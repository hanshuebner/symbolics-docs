"""Minimal S-expression parser for SAB_CODE_READ_FROM_STRING.

Only handles: lists, dotted pairs, symbols, strings, numbers.
"""


def parse_sexpr(s: str):
    """Parse a string as an S-expression and return a Python object."""
    tokens = _tokenize(s)
    if not tokens:
        return None
    result, _ = _parse_tokens(tokens, 0)
    return result


def _tokenize(s: str) -> list:
    tokens = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch.isspace():
            i += 1
        elif ch == '(':
            tokens.append('(')
            i += 1
        elif ch == ')':
            tokens.append(')')
            i += 1
        elif ch == '"':
            # string literal
            j = i + 1
            while j < len(s) and s[j] != '"':
                if s[j] == '\\':
                    j += 1
                j += 1
            tokens.append(s[i:j + 1])
            i = j + 1
        elif ch == "'":
            tokens.append("'")
            i += 1
        else:
            # atom (symbol or number)
            j = i
            while j < len(s) and s[j] not in '() \t\n\r"':
                j += 1
            tokens.append(s[i:j])
            i = j
    return tokens


def _parse_tokens(tokens, pos):
    if pos >= len(tokens):
        return None, pos

    tok = tokens[pos]

    if tok == '(':
        # list
        items = []
        pos += 1
        dotted = False
        while pos < len(tokens) and tokens[pos] != ')':
            if tokens[pos] == '.':
                dotted = True
                pos += 1
                continue
            item, pos = _parse_tokens(tokens, pos)
            items.append(item)
        pos += 1  # skip ')'
        if dotted and len(items) == 2:
            return (items[0], items[1]), pos
        return items, pos

    if tok == "'":
        item, pos = _parse_tokens(tokens, pos + 1)
        return ['quote', item], pos

    if tok == ')':
        return None, pos + 1

    # atom
    return _parse_atom(tok), pos


def _parse_atom(tok: str):
    if tok.startswith('"') and tok.endswith('"'):
        return tok[1:-1].replace('\\"', '"').replace('\\\\', '\\')

    # try integer
    try:
        return int(tok)
    except ValueError:
        pass

    # try float
    try:
        return float(tok)
    except ValueError:
        pass

    # symbol (lowercase it to match Scheme behavior)
    return tok.lower()
