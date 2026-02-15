"""Parsed SAB AST -> semantic XML output.

Produces a lossless intermediate XML representation of SAB document structure.
"""

import re
from xml.sax.saxutils import escape as _xml_escape, quoteattr as _quoteattr
from .sab_types import (
    SageRecord, SageEnvr, SageCommand, SageReference,
    SagePicture, SageFunctionSpec, SageExampleRecordMarker,
)
from .genera_charset import PARAGRAPH_MARKER, LINE_BREAK_MARKER
from .binary_graphics import binary_decode_graphics
from .svg_renderer import render_picture_to_svg

# Regex matching XML-illegal characters (control chars except \t, \n, \r)
_ILLEGAL_XML_CHARS = re.compile(
    '[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]'
)


def _sanitize(text: str) -> str:
    """Remove characters that are illegal in XML."""
    return _ILLEGAL_XML_CHARS.sub('\ufffd', text)


def xml_escape(text: str) -> str:
    return _xml_escape(_sanitize(text))


def quoteattr(text: str) -> str:
    return _quoteattr(_sanitize(text))


def emit_xml(file_attrs, records, index, source_path="") -> str:
    """Convert parsed SAB data to semantic XML string."""
    parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    parts.append(f'<sab-document source={quoteattr(source_path)}>')

    # File attributes
    parts.append('  <file-attributes>')
    if isinstance(file_attrs, list):
        for item in file_attrs:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                name = str(item[0])
                val = _format_attr_value(item[1])
                parts.append(f'    <attribute name={quoteattr(name)} value={quoteattr(val)} />')
    parts.append('  </file-attributes>')

    # Records
    for i, record in enumerate(records):
        parts.append(_emit_record(record, index[i] if i < len(index) else None, indent=2))

    # Index
    parts.append('  <index>')
    for item in index:
        parts.append(_emit_index_item(item, indent=4))
    parts.append('  </index>')

    parts.append('</sab-document>')
    return '\n'.join(parts)


def _format_attr_value(val):
    """Format a file attribute value as a string."""
    if isinstance(val, str):
        return val
    elif isinstance(val, (list, tuple)):
        return ' '.join(str(v) for v in val)
    else:
        return str(val)


def _indent(level):
    return ' ' * level


def _emit_record(record, index_item, indent=2):
    """Emit a single record as XML."""
    if not isinstance(record, SageRecord):
        return f'{_indent(indent)}<!-- non-record: {xml_escape(str(record)[:100])} -->'

    name = _get_record_name(record)
    type_str = str(record.type) if record.type else ''
    uid = ''
    if index_item:
        uid_val = _get_field_from_index(index_item, 'unique-id')
        if uid_val is not None:
            uid = f' unique-id={quoteattr(str(uid_val))}'

    parts = [f'{_indent(indent)}<record name={quoteattr(name)} type={quoteattr(type_str)}{uid}>']

    for field_name, field_val in record.fields:
        parts.append(f'{_indent(indent + 2)}<field name={quoteattr(field_name)}>')
        parts.append(_emit_value(field_val, indent + 4))
        parts.append(f'{_indent(indent + 2)}</field>')

    parts.append(f'{_indent(indent)}</record>')
    return '\n'.join(parts)


def _get_record_name(record):
    """Get the display name of a record."""
    name = record.name
    if isinstance(name, SageFunctionSpec):
        return name.name
    elif isinstance(name, str):
        return name
    else:
        return str(name)


def _get_field_from_index(index_item, field_name):
    """Get a field value from an index item tuple."""
    if not isinstance(index_item, (list, tuple)) or len(index_item) < 3:
        return None
    fields = index_item[2]
    for fn, fv in fields:
        if fn == field_name:
            return fv
    return None


def _emit_value(val, indent=0):
    """Emit a value (may be nested) as XML."""
    if isinstance(val, str):
        return _emit_text(val, indent)
    elif isinstance(val, (int, float)):
        return f'{_indent(indent)}<number value="{val}" />'
    elif isinstance(val, SageEnvr):
        return _emit_envr(val, indent)
    elif isinstance(val, SageCommand):
        return _emit_command(val, indent)
    elif isinstance(val, SageReference):
        return _emit_reference(val, indent)
    elif isinstance(val, SagePicture):
        return _emit_picture(val, indent)
    elif isinstance(val, SageFunctionSpec):
        return f'{_indent(indent)}<function-spec name={quoteattr(val.name)} />'
    elif isinstance(val, SageExampleRecordMarker):
        return f'{_indent(indent)}<example-record-marker type={quoteattr(str(val.type))} encoding={quoteattr(str(val.encoding))} />'
    elif isinstance(val, list):
        return _emit_list(val, indent)
    elif isinstance(val, tuple):
        parts = [f'{_indent(indent)}<tuple>']
        for item in val:
            parts.append(_emit_value(item, indent + 2))
        parts.append(f'{_indent(indent)}</tuple>')
        return '\n'.join(parts)
    elif isinstance(val, bytes):
        return f'{_indent(indent)}<binary-data length="{len(val)}" />'
    elif val is None:
        return f'{_indent(indent)}<null />'
    else:
        return f'{_indent(indent)}<unknown>{xml_escape(str(val))}</unknown>'


def _emit_text(text, indent=0):
    """Emit text, splitting on paragraph and line break markers."""
    if not text:
        return f'{_indent(indent)}<text />'

    parts = []
    segments = text.split(PARAGRAPH_MARKER)
    for i, seg in enumerate(segments):
        if i > 0:
            parts.append(f'{_indent(indent)}<para-break />')
        subsegments = seg.split(LINE_BREAK_MARKER)
        for j, subseg in enumerate(subsegments):
            if j > 0:
                parts.append(f'{_indent(indent)}<line-break />')
            if subseg:
                parts.append(f'{_indent(indent)}<text>{xml_escape(subseg)}</text>')
    return '\n'.join(parts) if parts else f'{_indent(indent)}<text />'


def _emit_envr(envr, indent=0):
    """Emit an environment."""
    name = str(envr.name) if envr.name else ''
    parts = [f'{_indent(indent)}<envr name={quoteattr(name)}>']

    if envr.mods:
        parts.append(f'{_indent(indent + 2)}<mods>')
        for mod_name, mod_val in envr.mods:
            parts.append(
                f'{_indent(indent + 4)}<mod name={quoteattr(str(mod_name))} '
                f'value={quoteattr(str(mod_val))} />'
            )
        parts.append(f'{_indent(indent + 2)}</mods>')

    for item in envr.contents_list:
        parts.append(_emit_value(item, indent + 2))

    parts.append(f'{_indent(indent)}</envr>')
    return '\n'.join(parts)


def _emit_command(cmd, indent=0):
    """Emit a command."""
    name = str(cmd.name) if cmd.name else ''
    if cmd.parameter is None or cmd.parameter == []:
        return f'{_indent(indent)}<command name={quoteattr(name)} />'

    parts = [f'{_indent(indent)}<command name={quoteattr(name)}>']
    parts.append(_emit_value(cmd.parameter, indent + 2))
    parts.append(f'{_indent(indent)}</command>')
    return '\n'.join(parts)


def _emit_reference(ref, indent=0):
    """Emit a reference."""
    topic = ''
    if isinstance(ref.topic, str):
        topic = ref.topic
    elif isinstance(ref.topic, SageFunctionSpec):
        topic = ref.topic.name

    attrs = [
        f'topic={quoteattr(topic)}',
        f'type={quoteattr(str(ref.type) if ref.type else "")}',
    ]
    if ref.unique_id is not None:
        attrs.append(f'unique-id={quoteattr(str(ref.unique_id))}')
    if ref.view is not None:
        attrs.append(f'view={quoteattr(str(ref.view))}')
    if ref.appearance is not None:
        attrs.append(f'appearance={quoteattr(str(ref.appearance))}')
    if ref.booleans:
        attrs.append(f'booleans={quoteattr(str(ref.booleans))}')
    if ref.field:
        attrs.append(f'field={quoteattr(str(ref.field))}')

    return f'{_indent(indent)}<reference {" ".join(attrs)} />'


def _emit_picture(pic, indent=0):
    """Emit a picture with decoded graphics."""
    attrs = [
        f'name={quoteattr(pic.name)}',
        f'type={quoteattr(str(pic.type) if pic.type else "")}',
    ]
    if pic.file_name:
        attrs.append(f'file-name={quoteattr(str(pic.file_name))}')

    parts = [f'{_indent(indent)}<picture {" ".join(attrs)}>']

    # Try to decode graphics
    if pic.contents:
        try:
            data = pic.contents if isinstance(pic.contents, bytes) else pic.contents.encode('latin-1')
            ops = binary_decode_graphics(data)
            svg = render_picture_to_svg(ops)
            parts.append(f'{_indent(indent + 2)}<graphics>')
            parts.append(svg)
            parts.append(f'{_indent(indent + 2)}</graphics>')
        except Exception as e:
            parts.append(f'{_indent(indent + 2)}<graphics-error>{xml_escape(str(e))}</graphics-error>')

    parts.append(f'{_indent(indent)}</picture>')
    return '\n'.join(parts)


def _emit_list(lst, indent=0):
    """Emit a list of values."""
    if not lst:
        return f'{_indent(indent)}<content-list />'

    parts = [f'{_indent(indent)}<content-list>']
    for item in lst:
        parts.append(_emit_value(item, indent + 2))
    parts.append(f'{_indent(indent)}</content-list>')
    return '\n'.join(parts)


def _emit_index_item(item, indent=0):
    """Emit an index item."""
    if not isinstance(item, (list, tuple)) or len(item) < 3:
        return f'{_indent(indent)}<!-- malformed index item -->'

    topic, type_sym, fields = item
    topic_str = ''
    if isinstance(topic, str):
        topic_str = topic
    elif isinstance(topic, SageFunctionSpec):
        topic_str = topic.name

    parts = [
        f'{_indent(indent)}<index-item '
        f'topic={quoteattr(topic_str)} '
        f'type={quoteattr(str(type_sym) if type_sym else "")}>'
    ]

    for field_name, field_val in fields:
        if field_name == 'callee-list' and isinstance(field_val, list):
            for callee in field_val:
                if isinstance(callee, (list, tuple)) and len(callee) >= 4:
                    callee_topic = callee[0]
                    if isinstance(callee_topic, SageFunctionSpec):
                        callee_topic = callee_topic.name
                    parts.append(
                        f'{_indent(indent + 2)}<callee '
                        f'topic={quoteattr(str(callee_topic))} '
                        f'type={quoteattr(str(callee[1]))} '
                        f'called-how={quoteattr(str(callee[2]))} '
                        f'unique-id={quoteattr(str(callee[3]))} />'
                    )
        else:
            parts.append(f'{_indent(indent + 2)}<index-field name={quoteattr(field_name)}>')
            parts.append(_emit_value(field_val, indent + 4))
            parts.append(f'{_indent(indent + 2)}</index-field>')

    parts.append(f'{_indent(indent)}</index-item>')
    return '\n'.join(parts)
