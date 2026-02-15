"""SAB type code constants and data structures.

Ports the Scheme *sab-code-names* list and associated structures.
"""

from dataclasses import dataclass, field
from typing import Any

# SAB type code constants (indices into *sab-code-names*)
SAB_CODE_RECORD = 0
SAB_CODE_TYPE_SYMBOL = 1
SAB_CODE_FUNCTION_SPEC = 2
SAB_CODE_FIELD_ALIST = 3
SAB_CODE_FIELD_NAME = 4
SAB_CODE_ENVR = 5
SAB_CODE_ENVR_NAME = 6
SAB_CODE_ENVR_MODS = 7
SAB_CODE_ATTRIBUTE_NAME = 8
SAB_CODE_CONTENTS_LIST = 9
SAB_CODE_FIXNUM = 10
SAB_CODE_STRING = 11
SAB_CODE_LONG_STRING = 12
SAB_CODE_LIST = 13
SAB_CODE_SYMBOL_REF = 14
SAB_CODE_UNINTERNED_SYMBOL_DEF = 15
SAB_CODE_SAGE_PKG_SYMBOL_DEF = 16
SAB_CODE_PKG_SYMBOL_DEF = 17
SAB_CODE_DOC_PKG_SYMBOL_DEF = 18
SAB_CODE_READ_FROM_STRING = 19
SAB_CODE_SIMPLE_COMMAND = 20
SAB_CODE_COMMAND = 21
SAB_CODE_SIMPLE_COMMAND_NAME = 22
SAB_CODE_COMMAND_NAME = 23
SAB_CODE_MACRO_CALL = 24
SAB_CODE_MACRO_NAME = 25
SAB_CODE_MACRO_ARGLIST = 26
SAB_CODE_LOCATION_PAIR = 27
SAB_CODE_INDEX = 28
SAB_CODE_CALLEE_TRIPLE_LIST = 29
SAB_CODE_INDEX_ITEM = 30
SAB_CODE_FILE_ATTRIBUTE_ALIST = 31
SAB_CODE_KEYWORD_PKG_SYMBOL_DEF = 32
SAB_CODE_REFERENCE = 33
SAB_CODE_FAT_STRING = 34
SAB_CODE_UNIQUE_ID = 35
SAB_CODE_MODIFICATION_HISTORY = 36
SAB_CODE_TOKEN_LIST = 37
SAB_CODE_FILE_ATTRIBUTE_STRING = 38
SAB_CODE_CALLEE_4PLE_LIST = 39
SAB_CODE_PICTURE = 40
SAB_CODE_8_BIT_ARRAY = 41
SAB_CODE_EXAMPLE_RECORD_MARKER = 42
SAB_CODE_EXTENSIBLE_REFERENCE = 43
SAB_CODE_EXTENSIBLE_REFERENCE_TAKE_TWO = 44
SAB_CODE_CHARACTER = 45

SAB_CODE_NAMES = [
    'record', 'type-symbol', 'function-spec', 'field-alist',
    'field-name', 'envr', 'envr-name', 'envr-mods',
    'attribute-name', 'contents-list', 'fixnum', 'string',
    'long-string', 'list', 'symbol-ref', 'uninterned-symbol-def',
    'sage-pkg-symbol-def', 'pkg-symbol-def', 'doc-pkg-symbol-def',
    'read-from-string', 'simple-command', 'command',
    'simple-command-name', 'command-name', 'macro-call',
    'macro-name', 'macro-arglist', 'location-pair',
    'index', 'callee-triple-list', 'index-item',
    'file-attribute-alist', 'keyword-pkg-symbol-def',
    'reference', 'fat-string', 'unique-id',
    'modification-history', 'token-list', 'file-attribute-string',
    'callee-4ple-list', 'picture', '8-bit-array',
    'example-record-marker', 'extensible-reference',
    'extensible-reference-take-two', 'character',
]

NUM_SAB_CODES = len(SAB_CODE_NAMES)

# Nil symbols from Lisp
LISP_NIL_SYMBOLS = frozenset(['lisp:nil', 'common-lisp:nil'])


class SymbolTable:
    """Accumulator for symbols defined during parsing. Replaces Scheme mytable."""
    __slots__ = ('symbols',)

    def __init__(self):
        self.symbols = []

    def add(self, sym):
        self.symbols.append(sym)

    def get(self, index):
        return self.symbols[index]


@dataclass
class SageRecord:
    name: Any
    type: Any
    fields: list  # list of (field_name, value) pairs
    index: Any = None
    callees: dict = field(default_factory=dict)


@dataclass
class SageEnvr:
    name: Any
    mods: list
    contents_list: list


@dataclass
class SageCommand:
    name: Any
    parameter: Any


@dataclass
class SageReference:
    topic: Any
    type: Any
    unique_id: Any
    view: Any
    appearance: Any
    booleans: Any
    field: Any


@dataclass
class SagePicture:
    type: Any
    file_name: Any
    name: str
    contents: Any
    decoded: Any = None


@dataclass
class SageFunctionSpec:
    name: str


@dataclass
class SageExampleRecordMarker:
    type: Any
    encoding: Any


# Field name -> expected SAB code mapping
# Ports *field-name-to-sab-code-alist* from the Scheme code
FIELD_NAME_TO_SAB_CODE = {
    'unique-id': SAB_CODE_UNIQUE_ID,
    'version-number': SAB_CODE_FIXNUM,
    'flags': SAB_CODE_FIXNUM,
    'location': SAB_CODE_LOCATION_PAIR,
    'tokens': SAB_CODE_TOKEN_LIST,
    'keywords': SAB_CODE_CONTENTS_LIST,
    'callee-list': SAB_CODE_CALLEE_4PLE_LIST,
    'source-topic': SAB_CODE_CONTENTS_LIST,
    'file-attribute-string': SAB_CODE_FILE_ATTRIBUTE_STRING,
    'contents': SAB_CODE_CONTENTS_LIST,
    'arglist': SAB_CODE_CONTENTS_LIST,
    'symbolics-common-lisp:arglist': SAB_CODE_CONTENTS_LIST,
    'modification-history': SAB_CODE_MODIFICATION_HISTORY,
    'source-title': SAB_CODE_CONTENTS_LIST,
    'oneliner': SAB_CODE_CONTENTS_LIST,
    'related': SAB_CODE_CONTENTS_LIST,
    'releasenumber': SAB_CODE_CONTENTS_LIST,
    'abbrev': SAB_CODE_CONTENTS_LIST,
    'notes': SAB_CODE_CONTENTS_LIST,
    'glossary': SAB_CODE_CONTENTS_LIST,
    'patched-from': SAB_CODE_STRING,
    'unique-index': SAB_CODE_FIXNUM,
}
