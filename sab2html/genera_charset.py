"""Genera character encoding -> Unicode mapping.

Ports the Scheme recode-genera-characters function and its character table.
"""

# Use Unicode Private Use Area chars as sentinels for markers
# These won't appear in any actual document text
PARAGRAPH_MARKER = "\ue000"
LINE_BREAK_MARKER = "\ue001"

# Genera special character codes -> Unicode
# From the Scheme chars list in recode-genera-characters
GENERA_CHAR_MAP = {
    0x00: '\u00b7',  # middle dot
    0x01: '\u2193',  # down arrow
    0x02: '\u03b1',  # alpha
    0x03: '\u03b2',  # beta
    0x04: '\u2227',  # logical and
    0x05: '\u00ac',  # not sign
    0x06: '\u03b5',  # epsilon
    0x07: '\u03c0',  # pi
    0x08: '\u03bb',  # lambda
    0x09: '\u03b3',  # gamma
    0x0a: '\u03b4',  # delta
    0x0b: '\u2191',  # up arrow
    0x0c: '\u00b1',  # plus-minus
    0x0d: '\u2295',  # circle-plus
    0x0e: '\u221e',  # infinity
    0x0f: '\u2202',  # partial derivative
    0x10: '\u2282',  # subset
    0x11: '\u2283',  # superset
    0x12: '\u222a',  # union
    0x13: '\u2229',  # intersection
    0x14: '\u2200',  # for all
    0x15: '\u2203',  # there exists
    0x16: '\u2297',  # circle-times
    0x17: '\u21c6',  # leftright arrows
    0x18: '\u2190',  # left arrow
    0x19: '\u2192',  # right arrow
    0x1a: '\u2260',  # not equal
    0x1b: '\u22c4',  # diamond
    0x1c: '\u2264',  # less than or equal
    0x1d: '\u2265',  # greater than or equal
    0x1e: '\u2261',  # identical to
    0x1f: '\u2228',  # logical or
}

# Characters in the C1 control range (0x7F-0x9F) that appear in Genera
# SAB files.  Most are formatting artifacts; strip them rather than
# producing U+FFFD replacement characters.
# 0x89 is a tab/indentation marker in Genera text — handled separately.
_C1_TAB = 0x89
_C1_STRIP = (set(range(0x7f, 0x8d)) | set(range(0x8e, 0xa0))) - {_C1_TAB}

_TAB_WIDTH = 8


def _recode_and_expand(text: str) -> str:
    """Recode Genera characters, expand 0x89 tabs to spaces.

    Handles paragraph markers (0x8D 0x8D), line breaks (0x8D),
    the 32 special character codes (0x00-0x1F), C1 control
    stripping, and column-aware tab expansion for 0x89.
    """
    # First handle paragraph markers and line breaks
    result = text.replace('\x8d\x8d', PARAGRAPH_MARKER)
    result = result.replace('\x8d', LINE_BREAK_MARKER)

    out = []
    col = 0
    for ch in result:
        code = ord(ch)
        if code == _C1_TAB:
            # Expand to spaces up to the next tab stop
            spaces = _TAB_WIDTH - (col % _TAB_WIDTH)
            out.append(' ' * spaces)
            col += spaces
        elif code in GENERA_CHAR_MAP:
            out.append(GENERA_CHAR_MAP[code])
            col += 1
        elif code in _C1_STRIP:
            pass  # silently drop unmapped C1 control characters
        elif ch == LINE_BREAK_MARKER or ch == '\n':
            out.append(ch)
            col = 0
        elif ch == PARAGRAPH_MARKER:
            out.append(ch)
            col = 0
        else:
            out.append(ch)
            col += 1
    return ''.join(out)


def recode_genera_characters(text: str) -> str:
    """Recode Genera-specific characters in a string to Unicode.

    Handles paragraph markers (0x8D 0x8D), line breaks (0x8D),
    the 32 special character codes, and tab expansion.
    """
    return _recode_and_expand(text)


def recode_genera_long_string(text: str) -> str:
    """Recode a long string - same handling as recode_genera_characters."""
    return _recode_and_expand(text)
