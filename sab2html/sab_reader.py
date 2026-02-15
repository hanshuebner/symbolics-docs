"""Main SAB parser with dispatch table.

Ports all 46 reader functions from the Scheme sab-reader.scm.
"""

import sys
from .stream import SabStream
from .sab_types import (
    SAB_CODE_RECORD, SAB_CODE_TYPE_SYMBOL, SAB_CODE_FUNCTION_SPEC,
    SAB_CODE_FIELD_ALIST, SAB_CODE_FIELD_NAME, SAB_CODE_ENVR,
    SAB_CODE_ENVR_NAME, SAB_CODE_ENVR_MODS, SAB_CODE_ATTRIBUTE_NAME,
    SAB_CODE_CONTENTS_LIST, SAB_CODE_FIXNUM, SAB_CODE_STRING,
    SAB_CODE_LONG_STRING, SAB_CODE_LIST, SAB_CODE_SYMBOL_REF,
    SAB_CODE_UNINTERNED_SYMBOL_DEF, SAB_CODE_SAGE_PKG_SYMBOL_DEF,
    SAB_CODE_PKG_SYMBOL_DEF, SAB_CODE_DOC_PKG_SYMBOL_DEF,
    SAB_CODE_READ_FROM_STRING, SAB_CODE_SIMPLE_COMMAND, SAB_CODE_COMMAND,
    SAB_CODE_SIMPLE_COMMAND_NAME, SAB_CODE_COMMAND_NAME,
    SAB_CODE_MACRO_CALL, SAB_CODE_MACRO_NAME, SAB_CODE_MACRO_ARGLIST,
    SAB_CODE_LOCATION_PAIR, SAB_CODE_INDEX, SAB_CODE_CALLEE_TRIPLE_LIST,
    SAB_CODE_INDEX_ITEM, SAB_CODE_FILE_ATTRIBUTE_ALIST,
    SAB_CODE_KEYWORD_PKG_SYMBOL_DEF, SAB_CODE_REFERENCE,
    SAB_CODE_FAT_STRING, SAB_CODE_UNIQUE_ID, SAB_CODE_MODIFICATION_HISTORY,
    SAB_CODE_TOKEN_LIST, SAB_CODE_FILE_ATTRIBUTE_STRING,
    SAB_CODE_CALLEE_4PLE_LIST, SAB_CODE_PICTURE, SAB_CODE_8_BIT_ARRAY,
    SAB_CODE_EXAMPLE_RECORD_MARKER, SAB_CODE_EXTENSIBLE_REFERENCE,
    SAB_CODE_EXTENSIBLE_REFERENCE_TAKE_TWO, SAB_CODE_CHARACTER,
    SAB_CODE_NAMES, NUM_SAB_CODES, LISP_NIL_SYMBOLS,
    SymbolTable, SageRecord, SageEnvr, SageCommand, SageReference,
    SagePicture, SageFunctionSpec, SageExampleRecordMarker,
    FIELD_NAME_TO_SAB_CODE,
)
from .genera_charset import recode_genera_characters, recode_genera_long_string
from .sexpr_parser import parse_sexpr

# Dispatch table: code -> reader function
_readers = [None] * NUM_SAB_CODES


def register_reader(code):
    """Decorator to register a reader function for a SAB type code."""
    def decorator(func):
        _readers[code] = func
        return func
    return decorator


def _is_nil(value):
    """Check if a value is a Lisp nil symbol."""
    return isinstance(value, str) and value in LISP_NIL_SYMBOLS


def read_sab_thing(stream: SabStream, table: SymbolTable, required_type=None):
    """Read a SAB thing from the stream. Core dispatch function."""
    code = stream.read_u8()
    if required_type is not None and code != required_type:
        raise ValueError(
            f"SAB code {code} ({SAB_CODE_NAMES[code] if code < NUM_SAB_CODES else '?'}) "
            f"instead of {required_type} ({SAB_CODE_NAMES[required_type]}) "
            f"at offset 0x{stream.offset:x}"
        )
    if code >= NUM_SAB_CODES or _readers[code] is None:
        raise ValueError(
            f"No SAB reader for code {code} "
            f"({SAB_CODE_NAMES[code] if code < NUM_SAB_CODES else '?'}) "
            f"at offset 0x{stream.offset:x}"
        )
    return _readers[code](stream, table)


def read_sab_string(stream: SabStream, table: SymbolTable) -> str:
    """Read a string (short or long) from the stream."""
    c = stream.peek()
    if c == SAB_CODE_STRING:
        return read_sab_thing(stream, table, SAB_CODE_STRING)
    elif c == SAB_CODE_LONG_STRING:
        return read_sab_thing(stream, table, SAB_CODE_LONG_STRING)
    else:
        raise ValueError(
            f"Wanted to read a string but got code {c} "
            f"({SAB_CODE_NAMES[c] if c < NUM_SAB_CODES else '?'}) "
            f"at offset 0x{stream.offset:x}"
        )


def _read_sab_symbol(stream, table, prefix):
    """Read a symbol definition, prepend prefix, add to table."""
    name = read_sab_string(stream, table)
    sym = prefix + name.lower()
    table.add(sym)
    return sym


# ========== Reader implementations ==========

@register_reader(SAB_CODE_RECORD)
def read_record(stream, table):
    name = read_sab_thing(stream, table, None)
    type_sym = read_sab_thing(stream, table, SAB_CODE_TYPE_SYMBOL)
    field_alist = read_sab_thing(stream, table, SAB_CODE_FIELD_ALIST)
    return SageRecord(name=name, type=type_sym, fields=field_alist)


@register_reader(SAB_CODE_TYPE_SYMBOL)
def read_type_symbol(stream, table):
    return read_sab_thing(stream, table, None)


@register_reader(SAB_CODE_FUNCTION_SPEC)
def read_function_spec(stream, table):
    name = read_sab_string(stream, table)
    return SageFunctionSpec(name=name)


@register_reader(SAB_CODE_FIELD_ALIST)
def read_field_alist(stream, table):
    n = stream.read_u16_le()
    result = []
    for _ in range(n):
        field_name, sab_code = read_sab_thing(stream, table, SAB_CODE_FIELD_NAME)
        value = read_sab_thing(stream, table, sab_code)
        result.append((field_name, value))
    return result


@register_reader(SAB_CODE_FIELD_NAME)
def read_field_name(stream, table):
    field_name = read_sab_thing(stream, table, None)
    # Look up field name (case-insensitive, since Scheme symbols are case-insensitive)
    lookup_name = field_name.lower() if isinstance(field_name, str) else field_name
    if lookup_name not in FIELD_NAME_TO_SAB_CODE:
        raise ValueError(f"Not a valid field name: {field_name!r}")
    sab_code = FIELD_NAME_TO_SAB_CODE[lookup_name]
    return (lookup_name, sab_code)


@register_reader(SAB_CODE_ENVR)
def read_envr(stream, table):
    envr_name = read_sab_thing(stream, table, SAB_CODE_ENVR_NAME)
    envr_mods = read_sab_thing(stream, table, SAB_CODE_ENVR_MODS)
    contents_list = read_sab_thing(stream, table, SAB_CODE_CONTENTS_LIST)
    return SageEnvr(name=envr_name, mods=envr_mods, contents_list=contents_list)


@register_reader(SAB_CODE_ENVR_NAME)
def read_envr_name(stream, table):
    return read_sab_thing(stream, table, None)


@register_reader(SAB_CODE_ENVR_MODS)
def read_envr_mods(stream, table):
    n = stream.read_u16_le()
    result = []
    for _ in range(n):
        name = read_sab_thing(stream, table, SAB_CODE_ATTRIBUTE_NAME)
        val = read_sab_thing(stream, table, None)
        result.append((name, val))
    return result


@register_reader(SAB_CODE_ATTRIBUTE_NAME)
def read_attribute_name(stream, table):
    return read_sab_thing(stream, table, None)


@register_reader(SAB_CODE_CONTENTS_LIST)
def read_contents_list(stream, table):
    n = stream.read_u16_le()
    return [read_sab_thing(stream, table, None) for _ in range(n)]


@register_reader(SAB_CODE_FIXNUM)
def read_fixnum(stream, table):
    return stream.read_u32_le()


@register_reader(SAB_CODE_STRING)
def read_string(stream, table):
    size = stream.read_u8()
    raw = stream.read_bytes(size).decode('latin-1')
    return recode_genera_characters(raw)


@register_reader(SAB_CODE_LONG_STRING)
def read_long_string(stream, table):
    size = stream.read_u32_le()
    raw = stream.read_bytes(size).decode('latin-1')
    return recode_genera_long_string(raw)


@register_reader(SAB_CODE_LIST)
def read_list(stream, table):
    n = stream.read_u16_le()
    return [read_sab_thing(stream, table, None) for _ in range(n)]


@register_reader(SAB_CODE_SYMBOL_REF)
def read_symbol_ref(stream, table):
    index = stream.read_u16_le()
    return table.get(index)


@register_reader(SAB_CODE_UNINTERNED_SYMBOL_DEF)
def read_uninterned_symbol_def(stream, table):
    return _read_sab_symbol(stream, table, "uninterned:")


@register_reader(SAB_CODE_SAGE_PKG_SYMBOL_DEF)
def read_sage_pkg_symbol_def(stream, table):
    return _read_sab_symbol(stream, table, "")


@register_reader(SAB_CODE_PKG_SYMBOL_DEF)
def read_pkg_symbol_def(stream, table):
    pkg = read_sab_string(stream, table)
    return _read_sab_symbol(stream, table, pkg + ":")


@register_reader(SAB_CODE_DOC_PKG_SYMBOL_DEF)
def read_doc_pkg_symbol_def(stream, table):
    return _read_sab_symbol(stream, table, "doc:")


@register_reader(SAB_CODE_KEYWORD_PKG_SYMBOL_DEF)
def read_keyword_pkg_symbol_def(stream, table):
    return _read_sab_symbol(stream, table, ":")


@register_reader(SAB_CODE_READ_FROM_STRING)
def read_read_from_string(stream, table):
    s = read_sab_string(stream, table)
    return parse_sexpr(s)


@register_reader(SAB_CODE_SIMPLE_COMMAND)
def read_simple_command(stream, table):
    # Simple command: just a name, no parameter
    name = read_sab_thing(stream, table, SAB_CODE_SIMPLE_COMMAND_NAME)
    cmd = SageCommand(name=name, parameter=None)
    return cmd


@register_reader(SAB_CODE_COMMAND)
def read_command(stream, table):
    name = read_sab_thing(stream, table, SAB_CODE_COMMAND_NAME)
    parameter = read_sab_thing(stream, table, None)
    if _is_nil(parameter):
        parameter = []
    return SageCommand(name=name, parameter=parameter)


@register_reader(SAB_CODE_SIMPLE_COMMAND_NAME)
def read_simple_command_name(stream, table):
    return read_sab_thing(stream, table, None)


@register_reader(SAB_CODE_COMMAND_NAME)
def read_command_name(stream, table):
    name = read_sab_thing(stream, table, None)
    return name


@register_reader(SAB_CODE_MACRO_CALL)
def read_macro_call(stream, table):
    name = read_sab_thing(stream, table, SAB_CODE_MACRO_NAME)
    arglist = read_sab_thing(stream, table, SAB_CODE_MACRO_ARGLIST)
    return SageCommand(name=name, parameter=arglist)


@register_reader(SAB_CODE_MACRO_NAME)
def read_macro_name(stream, table):
    return read_sab_thing(stream, table, None)


@register_reader(SAB_CODE_MACRO_ARGLIST)
def read_macro_arglist(stream, table):
    return read_sab_thing(stream, table, None)


@register_reader(SAB_CODE_LOCATION_PAIR)
def read_location_pair(stream, table):
    from_val = read_sab_thing(stream, table, SAB_CODE_FIXNUM)
    to_val = read_sab_thing(stream, table, SAB_CODE_FIXNUM)
    return (from_val, to_val)


@register_reader(SAB_CODE_INDEX)
def read_index(stream, table):
    n = stream.read_u32_le()
    return [read_sab_thing(stream, table, SAB_CODE_INDEX_ITEM) for _ in range(n)]


@register_reader(SAB_CODE_CALLEE_TRIPLE_LIST)
def read_callee_triple_list(stream, table):
    # Old format, kept for compatibility
    n = stream.read_u16_le()
    result = []
    for _ in range(n):
        topic = read_sab_thing(stream, table, None)
        type_sym = read_sab_thing(stream, table, SAB_CODE_TYPE_SYMBOL)
        called_how = read_sab_thing(stream, table, None)
        result.append((topic, type_sym, called_how))
    return result


@register_reader(SAB_CODE_INDEX_ITEM)
def read_index_item(stream, table):
    topic = read_sab_thing(stream, table, None)
    type_sym = read_sab_thing(stream, table, SAB_CODE_TYPE_SYMBOL)
    n = stream.read_u16_le()
    fields = []
    for _ in range(n):
        field_name, sab_code = read_sab_thing(stream, table, SAB_CODE_FIELD_NAME)
        value = read_sab_thing(stream, table, sab_code)
        fields.append((field_name, value))
    return (topic, type_sym, fields)


@register_reader(SAB_CODE_FILE_ATTRIBUTE_ALIST)
def read_file_attribute_alist(stream, table):
    alist = read_sab_thing(stream, table, None)
    return alist


@register_reader(SAB_CODE_REFERENCE)
def read_reference(stream, table):
    topic = read_sab_thing(stream, table, None)
    type_sym = read_sab_thing(stream, table, SAB_CODE_TYPE_SYMBOL)
    unique_id = read_sab_thing(stream, table, None)
    view = read_sab_thing(stream, table, None)
    field = read_sab_thing(stream, table, None)
    if _is_nil(field):
        field = []
    return SageReference(
        topic=topic, type=type_sym, unique_id=unique_id,
        view=view, appearance=None, booleans=[], field=field,
    )


@register_reader(SAB_CODE_EXTENSIBLE_REFERENCE)
def read_extensible_reference(stream, table):
    # Same as reference for our purposes
    return read_reference.__wrapped__(stream, table) if hasattr(read_reference, '__wrapped__') else _readers[SAB_CODE_REFERENCE](stream, table)


@register_reader(SAB_CODE_EXTENSIBLE_REFERENCE_TAKE_TWO)
def read_extensible_reference_take_two(stream, table):
    topic = read_sab_thing(stream, table, None)
    type_sym = read_sab_thing(stream, table, SAB_CODE_TYPE_SYMBOL)
    unique_id = read_sab_thing(stream, table, None)
    view = read_sab_thing(stream, table, None)
    appearance = read_sab_thing(stream, table, None)
    booleans = read_sab_thing(stream, table, None)
    field = read_sab_thing(stream, table, None)
    if _is_nil(booleans):
        booleans = []
    if _is_nil(field):
        field = []
    return SageReference(
        topic=topic, type=type_sym, unique_id=unique_id,
        view=view, appearance=appearance, booleans=booleans, field=field,
    )


@register_reader(SAB_CODE_FAT_STRING)
def read_fat_string(stream, table):
    """Read a fat string with font information.

    The fat string format is somewhat complex and not fully documented.
    We extract the text content and discard font styling info.
    """
    dimension_count = stream.read_u8()
    dims = [stream.read_u8() for _ in range(dimension_count)]
    total_len = dims[0] if dims else 0

    if len(dims) > 1 and dims[1] > 0:
        # Read and discard font specification bytes
        for _ in range(dims[1]):
            stream.read_u8()

        if dims[1] > 0:
            type_byte = stream.read_u8()
            if type_byte == 0x0c:
                fst_len = stream.read_u8()
                stream.read_bytes(fst_len)  # discard first string
                snd_len = stream.read_u8()
                stream.read_bytes(snd_len)  # discard second string
                ten = stream.read_u8()
                if ten != 0x10:
                    raise ValueError(f"Expected 0x10 in fat string, got 0x{ten:02x}")
            elif type_byte == 0x14:
                style_len = stream.read_u8()
                stream.read_bytes(style_len)  # discard style
                next_byte = stream.read_u8()
                if next_byte == 0x14:
                    style_len2 = stream.read_u8()
                    stream.read_bytes(style_len2)  # discard second style
                elif next_byte != 0x10:
                    raise ValueError(
                        f"Expected 0x10 or 0x14 in fat string, got 0x{next_byte:02x} "
                        f"at offset 0x{stream.offset:x}"
                    )
            else:
                raise ValueError(f"Unknown fat string type code 0x{type_byte:02x}")

            # Read font name
            font_len = stream.read_u8()
            stream.read_bytes(font_len)  # discard font name
            zero = stream.read_u8()
            if zero != 0:
                raise ValueError(f"Expected 0x00 in fat string, got 0x{zero:02x}")

    # Read the actual text content in chunks
    result = b''
    while len(result) < total_len:
        strlen = stream.read_u8()
        stream.read_u8()  # unknown byte, discard
        result += stream.read_bytes(strlen)

    text = result.decode('latin-1')
    return recode_genera_long_string(text)


@register_reader(SAB_CODE_UNIQUE_ID)
def read_unique_id(stream, table):
    return read_sab_thing(stream, table, None)


@register_reader(SAB_CODE_MODIFICATION_HISTORY)
def read_modification_history(stream, table):
    return read_sab_thing(stream, table, None)


@register_reader(SAB_CODE_TOKEN_LIST)
def read_token_list(stream, table):
    return read_sab_thing(stream, table, None)


@register_reader(SAB_CODE_FILE_ATTRIBUTE_STRING)
def read_file_attribute_string(stream, table):
    s = read_sab_string(stream, table)
    return s if s else None


@register_reader(SAB_CODE_CALLEE_4PLE_LIST)
def read_callee_4ple_list(stream, table):
    n = stream.read_u16_le()
    result = []
    for _ in range(n):
        topic = read_sab_thing(stream, table, None)
        type_sym = read_sab_thing(stream, table, SAB_CODE_TYPE_SYMBOL)
        called_how = read_sab_thing(stream, table, None)
        unique_id = read_sab_thing(stream, table, None)
        result.append((topic, type_sym, called_how, unique_id))
    return result


@register_reader(SAB_CODE_PICTURE)
def read_picture(stream, table):
    pic_type = read_sab_thing(stream, table, None)
    file_name = read_sab_thing(stream, table, None)
    name = read_sab_string(stream, table)
    contents = read_sab_thing(stream, table, None)
    return SagePicture(
        type=pic_type, file_name=file_name,
        name=name, contents=contents,
    )


@register_reader(SAB_CODE_8_BIT_ARRAY)
def read_8_bit_array(stream, table):
    n = stream.read_u32_le()
    return stream.read_bytes(n)


@register_reader(SAB_CODE_EXAMPLE_RECORD_MARKER)
def read_example_record_marker(stream, table):
    type_val = read_sab_thing(stream, table, None)
    encoding = read_sab_thing(stream, table, None)
    return SageExampleRecordMarker(type=type_val, encoding=encoding)


@register_reader(SAB_CODE_CHARACTER)
def read_character(stream, table):
    cs = read_sab_string(stream, table)
    if len(cs) == 1:
        return cs
    # The recoding may have expanded a single byte (e.g. 0x8D -> LINE_BREAK_MARKER)
    # In that case, return the expanded form
    return cs


# ========== Top-level SAB file reader ==========

SAGE_ID_PATTERN = 0
COMPILED_DATA_FORMAT_VERSIONS = {7}


def read_sab(filename: str):
    """Read and parse a SAB file.

    Returns (file_attribute_alist, records, index).
    """
    with open(filename, 'rb') as f:
        data = f.read()

    stream = SabStream(data, 0)

    # Read and validate header
    id_pattern = stream.read_u32_le()
    if id_pattern != SAGE_ID_PATTERN:
        raise ValueError(f"Not a SAB file (bad id pattern): {filename}")

    version = stream.read_u8()
    if version not in COMPILED_DATA_FORMAT_VERSIONS:
        raise ValueError(f"Incompatible SAB version {version} in {filename}")

    # Read file attribute alist (with fresh symbol table)
    file_attribute_alist = read_sab_thing(stream, SymbolTable(), SAB_CODE_FILE_ATTRIBUTE_ALIST)

    # Read section pointers
    ps = stream.read_u32_le()   # records section offset
    pos = stream.read_u32_le()  # index section offset

    # Read records (each with fresh symbol table per the Scheme code)
    stream.seek(ps)
    records = []
    while stream.offset < pos:
        record = read_sab_thing(stream, SymbolTable(), None)
        records.append(record)

    # Read index (with fresh symbol table)
    stream.seek(pos)
    index = read_sab_thing(stream, SymbolTable(), SAB_CODE_INDEX)

    return (file_attribute_alist, records, index)


def read_sab_index_only(filename: str):
    """Read only the file attributes and index section (fast path for pass 1).

    Returns (file_attribute_alist, index).
    """
    with open(filename, 'rb') as f:
        data = f.read()

    stream = SabStream(data, 0)

    id_pattern = stream.read_u32_le()
    if id_pattern != SAGE_ID_PATTERN:
        raise ValueError(f"Not a SAB file: {filename}")

    version = stream.read_u8()
    if version not in COMPILED_DATA_FORMAT_VERSIONS:
        raise ValueError(f"Incompatible SAB version: {version}")

    file_attribute_alist = read_sab_thing(stream, SymbolTable(), SAB_CODE_FILE_ATTRIBUTE_ALIST)

    ps = stream.read_u32_le()
    pos = stream.read_u32_le()

    # Skip directly to index
    stream.seek(pos)
    index = read_sab_thing(stream, SymbolTable(), SAB_CODE_INDEX)

    return (file_attribute_alist, index)
