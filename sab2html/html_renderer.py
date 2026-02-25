"""Semantic XML / parsed AST -> HTML conversion.

Ports the Scheme sage->sxml function with all environment and command cases.
This renders directly from parsed SAB structures to HTML strings.
"""

import re
from xml.sax.saxutils import escape as _xml_escape

_ILLEGAL_XML_CHARS = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]')

def xml_escape(text: str) -> str:
    return _xml_escape(_ILLEGAL_XML_CHARS.sub('\ufffd', text))
from .sab_types import (
    SageRecord, SageEnvr, SageCommand, SageReference,
    SagePicture, SageFunctionSpec, SageExampleRecordMarker,
)
from .genera_charset import PARAGRAPH_MARKER, LINE_BREAK_MARKER
from .binary_graphics import binary_decode_graphics
from .svg_renderer import render_picture_to_svg

# Sentinel for paragraph marker and tab-to-tab-stop
_PARAGRAPH_MARKER = object()
_TAB_MARKER = object()

_SLUG_RE = re.compile(r'[^a-z0-9]+')

def _slugify(name):
    """Convert a record/topic name to a URL-safe anchor ID."""
    s = str(name).lower()
    s = _SLUG_RE.sub('-', s).strip('-')
    return s or 'section'


_STRUCTURAL_TYPES = frozenset({
    'section', 'subsection', 'subsubsection', 'chapter',
})

def render_record_to_html(record, registry=None, current_file=None, heading_tag='h2'):
    """Render a SageRecord to an HTML section string."""
    title_html = _format_record_title(record)
    contents = _get_field(record, 'contents')
    if contents is None:
        contents = []

    ctx = RenderContext(registry=registry, current_file=current_file, record=record)
    body_parts = _render_content_list(contents, ctx)

    name = record.name
    if isinstance(name, SageFunctionSpec):
        name = name.name
    anchor = _slugify(name)

    rec_type = str(record.type).lower() if record.type else ''
    is_entry = rec_type not in _STRUCTURAL_TYPES
    cls = f' class="entry"' if is_entry else ''

    if is_entry:
        # Structured heading: name + arglist + type label
        arglist = _get_field(record, 'arglist') or _get_field(record, 'symbolics-common-lisp:arglist')
        arglist_html = ''
        if arglist:
            arglist_html = _render_content_list(arglist, ctx).strip()

        type_label = _format_type_label(record.type)

        heading_parts = [f'<span class="entry-name">{title_html}</span>']
        if arglist_html:
            heading_parts.append(f'<span class="entry-args">{arglist_html}</span>')
        if type_label:
            heading_parts.append(f'<span class="entry-type">{type_label}</span>')

        heading_inner = '\n  '.join(heading_parts)
        heading = f'<{heading_tag} class="entry-heading">\n  {heading_inner}\n</{heading_tag}>'
    else:
        heading = f'<{heading_tag}>{title_html}</{heading_tag}>'

    return (
        f'<section id="{anchor}"{cls}>\n'
        f'{heading}\n'
        f'{body_parts}\n'
        f'</section>\n'
    )


def render_records_to_html(records, index=None, registry=None, current_file=None,
                           title="", file_attrs=None):
    """Render a list of records to a full HTML page."""
    parts = []
    for i, record in enumerate(records):
        if not isinstance(record, SageRecord):
            continue
        # Associate index callees with record
        if index and i < len(index):
            _setup_record_callees(record, index[i])
        tag = 'h1' if i == 0 else 'h2'
        parts.append(render_record_to_html(record, registry, current_file, heading_tag=tag))

    body = '\n'.join(parts)
    page_title = title or "SAB Document"

    return (
        f'<!DOCTYPE html>\n'
        f'<html lang="en">\n'
        f'<head>\n'
        f'  <meta charset="utf-8">\n'
        f'  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'  <title>{xml_escape(page_title)}</title>\n'
        f'  <link rel="stylesheet" href="{{{{CSS_PATH}}}}">\n'
        f'</head>\n'
        f'<body>\n'
        f'<header class="site-header">\n'
        f'  <div class="header-left">\n'
        f'    <a href="{{{{INDEX_PATH}}}}" class="header-logo">\n'
        f'      <img src="{{{{LOGO_PATH}}}}" alt="Symbolics">\n'
        f'    </a>\n'
        f'    <span class="header-title">Portable Genera 9.0 Documentation</span>\n'
        f'  </div>\n'
        f'  <div class="header-search">\n'
        f'    <input type="text" id="header-search-input" placeholder="Search documentation..." autocomplete="off">\n'
        f'    <div id="header-search-results" class="search-dropdown"></div>\n'
        f'  </div>\n'
        f'</header>\n'
        f'<main class="content">\n'
        f'{body}\n'
        f'</main>\n'
        f'<script src="{{{{SEARCH_JS_PATH}}}}"></script>\n'
        f'</body>\n'
        f'</html>\n'
    )


class RenderContext:
    """Context for rendering, tracks current record and registry."""
    __slots__ = ('registry', 'current_file', 'record', '_including')

    def __init__(self, registry=None, current_file=None, record=None):
        self.registry = registry
        self.current_file = current_file
        self.record = record
        self._including = set()


def _setup_record_callees(record, index_item):
    """Extract callee info from index item and attach to record."""
    if not isinstance(index_item, (list, tuple)) or len(index_item) < 3:
        return
    fields = index_item[2]
    callees = {}
    for fname, fval in fields:
        if fname == 'callee-list' and isinstance(fval, list):
            for c in fval:
                if isinstance(c, (list, tuple)) and len(c) >= 4:
                    callees[c[3]] = (c[1], c[2], c[0])  # (type, called_how, topic)
    record.callees = callees


def _get_field(record, name):
    """Get a field value from a record's field alist."""
    for fname, fval in record.fields:
        if fname == name:
            return fval
    return None


def _format_record_title(record):
    """Format the title of a record for HTML."""
    source_title = _get_field(record, 'source-title')
    if source_title and isinstance(source_title, list) and source_title:
        ctx = RenderContext()
        return _render_content_list(source_title, ctx)
    name = record.name
    if isinstance(name, SageFunctionSpec):
        return xml_escape(name.name)
    return xml_escape(str(name))


def _format_type_label(record_type):
    """Format record type for display: strip package prefix, title-case."""
    if not record_type:
        return ''
    s = str(record_type)
    # Strip package prefix like 'LISP:' or 'SYMBOLICS-COMMON-LISP:'
    if ':' in s:
        s = s.rsplit(':', 1)[1]
    return s.strip().title()


def _strip_package_prefix(name):
    """Strip Lisp package prefix for display: 'LISP:first' -> 'first'."""
    if ':' in name and not name.startswith(':'):
        return name.split(':', 1)[1]
    return name


def _resolve_l_command(param_text, ctx):
    """Resolve a Lisp symbol name to an href, or None."""
    if not ctx or not ctx.registry:
        return None
    stripped = _strip_package_prefix(param_text)
    registry = ctx.registry
    for candidate in (stripped, stripped.upper(), stripped.lower()):
        if candidate in registry.by_name:
            info = registry.by_name[candidate]
            relpath, uid, type_sym = info
            html_path = registry.get_html_path(relpath)
            anchor = _slugify(candidate)
            if ctx.current_file and html_path == ctx.current_file:
                return f'#{anchor}'
            if ctx.current_file:
                current_dir = os.path.dirname(ctx.current_file)
                html_path = os.path.relpath(html_path, current_dir)
            return f'{html_path}#{anchor}'
    return None


def _render_content_list_raw(contents, ctx):
    """Render a list of content items to HTML without paragraph fixup.

    Paragraph markers in text strings become newlines instead of <p> tags,
    since this is used for pre-wrap environments like display.
    """
    if not contents:
        return ''
    cleaned = []
    for item in contents:
        if isinstance(item, str):
            cleaned.append(item.replace(PARAGRAPH_MARKER, '\n'))
        elif item is _PARAGRAPH_MARKER:
            cleaned.append('\n')
        else:
            cleaned.append(item)
    parts = [_render_sage(item, ctx) for item in cleaned]
    return ''.join(parts)


def _render_content_list(contents, ctx):
    """Render a list of content items to HTML string."""
    if not contents:
        return ''
    # Apply paragraph/tab fixup
    processed = _fix_up_special_markup(contents)
    parts = [_render_sage(item, ctx) for item in processed]
    return ''.join(parts)


def _render_sage(sage, ctx):
    """Render a single sage object to HTML. Main dispatch function."""
    if isinstance(sage, str):
        return _render_text(sage)
    if sage is None or sage == []:
        return ''
    if isinstance(sage, SageEnvr):
        return _render_envr(sage, ctx)
    if isinstance(sage, SageCommand):
        return _render_command(sage, ctx)
    if isinstance(sage, SageReference):
        return _render_reference(sage, ctx)
    if isinstance(sage, SagePicture):
        return _render_picture(sage, ctx)
    if isinstance(sage, SageExampleRecordMarker):
        return '<div class="example-record-marker"></div>'
    if sage is _PARAGRAPH_MARKER:
        return '</p>\n<p>'
    if isinstance(sage, list):
        return ''.join(_render_sage(item, ctx) for item in sage)
    return xml_escape(str(sage))


def _render_text(text):
    """Render text, converting markers to HTML.

    LINE_BREAK_MARKER becomes a plain newline: in <pre> blocks this
    preserves the line break; in flowing text the browser collapses it
    to a space, which is the correct behaviour for filled paragraphs.
    """
    result = xml_escape(text)
    result = result.replace(PARAGRAPH_MARKER, '</p>\n<p>')
    result = result.replace(LINE_BREAK_MARKER, '\n')
    return result


def _render_envr(envr, ctx):
    """Render an environment to HTML."""
    content = _render_content_list(envr.contents_list, ctx)
    name = str(envr.name).lower() if envr.name else ''

    # Font environments
    if name == 'b':
        return f'<b>{content}</b>'
    if name == 'bi':
        return f'<b><i>{content}</i></b>'
    if name == 'i':
        return f'<i>{content}</i>'
    if name in ('r', 'g', 'w', 'p', 's', 'f'):
        return f'<span class="{name}">{content}</span>'
    if name in ('k', 'm', 'ls', 't'):
        return f'<code class="{name}">{content}</code>'
    if name == 'c':
        return f'<span class="pathname">{content}</span>'
    if name in ('u', 'un', 'ux'):
        return f'<span class="underline">{content}</span>'

    # Structure environments
    if name == 'example':
        return f'<div class="example"><pre>{content}</pre></div>'
    if name == 'display':
        raw = _render_content_list_raw(envr.contents_list, ctx)
        return f'<div class="display">{raw.strip()}</div>'
    if name == 'enumerate':
        items = _extract_list_items(envr.contents_list, ctx)
        return f'<ol class="enumerate">{items}</ol>'
    if name == 'itemize':
        items = _extract_list_items(envr.contents_list, ctx)
        return f'<ul class="itemize">{items}</ul>'
    if name == 'verbatim':
        return f'<pre class="verbatim">{content}</pre>'
    if name == 'description':
        return f'<div class="description">{content}</div>'
    if name == 'center':
        return f'<div class="center">{content}</div>'
    if name == 'figure':
        return f'<div class="figure">{content}</div>'
    if name == 'group':
        return f'<div class="group">{content}</div>'
    if name == 'multiple':
        return f'<div class="multiple">{content}</div>'
    if name == 'commentary':
        return f'<div class="commentary">{content}</div>'

    # Heading environments
    if name == 'header':
        return f'<h3 class="header">{content}</h3>'
    if name == 'heading':
        return f'<h4 class="heading">{content}</h4>'
    if name == 'majorheading':
        return f'<h3 class="majorheading">{content}</h3>'

    # Lisp sub/superscript
    if name in ('common-lisp:-', 'lisp:-'):
        return f'<sub>{content}</sub>'
    if name in ('common-lisp:+', 'lisp:+'):
        return f'<sup>{content}</sup>'
    if name in ('lisp:t', 'common-lisp:t'):
        return f'<span class="true">{content}</span>'

    # Format environments
    if name in ('lisp:format', 'common-lisp:format', 'global:format'):
        return f'<div class="format">{content}</div>'

    # Tab/paragraph structure (from fixup)
    if name == 'nex-tab-to-tab-stop':
        return f'<span class="tab-stop">{content}</span>'
    if name == 'nex-paragraph':
        return f'<p>{content}</p>'

    # Various other environments - render with class
    known_classes = {
        'quotation', 'advancednote', 'plus', 'minus', 'crossref',
        'table', 'simpletable', 'checklist', 'equation', 'verse',
        'text', 'level', 'flushright', 'flushleft', 'inputexample',
        'fileexample', 'programexample', 'outputexample', 'activeexample',
        'box', 'subheading', 'subsubheading', 'captionenv',
        'common-lisp:block', 'lisp:block', 'c-description',
        'bar', 'old-bar-environment', 'largestyle', 'titlestyle',
        'transparent', 'layerederrorenv', 'lisp:float', 'fullpagefigure',
        'fullpagetable',
    }
    if name in known_classes:
        return f'<div class="{xml_escape(name)}">{content}</div>'

    # Unknown environment
    return f'<div class="unknown-env" data-name="{xml_escape(name)}">{content}</div>'


def _extract_list_items(contents, ctx):
    """Extract list items from contents, using paragraph breaks as item separators."""
    processed = _fix_up_special_markup(contents)
    items = []
    current = []
    for item in processed:
        if isinstance(item, SageEnvr) and str(item.name) == 'nex-paragraph':
            if current:
                items.append(''.join(current))
                current = []
            items.append(_render_content_list(item.contents_list, ctx))
        else:
            current.append(_render_sage(item, ctx))
    if current:
        items.append(''.join(current))

    if not items:
        return _render_content_list(contents, ctx)

    return '\n'.join(f'<li>{item}</li>' for item in items if item.strip())


def _render_command(cmd, ctx):
    """Render a command to HTML."""
    name = str(cmd.name) if cmd.name else ''

    if name == 'em':
        return '\u2014'  # em dash
    if name == 'force-line-break':
        return '<br>'
    if name == 'literal-space':
        return ' '
    if name == 'permit-word-break':
        return '\u200b'  # zero-width space
    if name == 'ignore-white-space':
        return ''
    if name == 'tab-to-tab-stop':
        return '<span class="tab-stop"></span>'

    if name == 'subsection':
        param_text = _extract_param_text(cmd.parameter)
        return f'<h4>{param_text}</h4>'

    if name == 'blankspace':
        return _render_blankspace(cmd.parameter)

    if name == 'tag':
        anchor = _extract_param_text(cmd.parameter)
        return f'<a id="{xml_escape(anchor)}" class="tag"></a>'

    if name == 'label':
        anchor = _extract_param_text(cmd.parameter)
        return f'<a id="{xml_escape(anchor)}" class="label"></a>'

    if name == 'ref':
        target = _extract_param_text(cmd.parameter)
        return f'<a href="#{xml_escape(target)}">{xml_escape(target)}</a>'

    if name == 'index':
        return ''  # Index entries are invisible in HTML

    if name == 'l':
        param_text = _extract_param_text(cmd.parameter)
        display_text = _strip_package_prefix(param_text)
        href = _resolve_l_command(param_text, ctx)
        if href:
            return f'<b><a href="{href}">{xml_escape(display_text)}</a></b>'
        return f'<b>{xml_escape(display_text)}</b>'

    if name == 'value':
        param_text = _extract_param_text(cmd.parameter)
        return f'<var>{xml_escape(param_text)}</var>'

    if name == 'caption':
        param_text = _extract_param_text(cmd.parameter)
        return f'<div class="caption">{xml_escape(param_text)}</div>'

    if name == 'newpage':
        return '<hr class="page-break">'

    # Various commands that we render as nothing or with class
    silent_commands = {
        'indexsecondary', 'tabdivide', 'permanentstring',
        'collect-centering', 'collect-right-flushing',
        'dynamic-left-margin', 'plainheadingsnow', 'plainheadings',
        'pagefooting', 'pageheading', 'pageref', 'blocklabel',
        'hinge', 'make', 'tabclear', 'tabset',
        'endexamplecompiledprologue', 'replicate-pattern',
        'simpletablespecs', 'dictionarytabs', 'note', 'bar',
        'abbreviation-period', 'missing-special-character',
        'layerederror', 'include', 'lisp:case',
        'common-lisp:string', 'lisp:string',
    }
    if name in silent_commands:
        return ''

    # Unknown command
    return ''


def _render_blankspace(parameter):
    """Render a blankspace command to a sized div."""
    if not parameter:
        return '<div class="blankspace" style="height: 1em;"></div>'

    try:
        el = parameter
        if isinstance(el, list) and el:
            el = el[0]
        if isinstance(el, list):
            if len(el) == 3:
                count, unit = el[1], el[2]
            elif len(el) == 2:
                count, unit = el[0], el[1]
            else:
                return '<div class="blankspace" style="height: 1em;"></div>'
        else:
            return '<div class="blankspace" style="height: 1em;"></div>'

        unit_str = str(unit)
        if unit_str == 'lines':
            height = f"{count}em"
        elif unit_str == 'inches':
            height = f"{count}in"
        elif unit_str == 'cm':
            height = f"{count}cm"
        else:
            height = f"{count}em"

        return f'<div class="blankspace" style="height: {height};"></div>'
    except Exception:
        return '<div class="blankspace" style="height: 1em;"></div>'


def _extract_param_text(parameter):
    """Extract text from a command parameter."""
    if isinstance(parameter, str):
        return parameter
    if isinstance(parameter, list):
        if not parameter:
            return ''
        first = parameter[0]
        if isinstance(first, str):
            return first
        if isinstance(first, list) and first:
            return str(first[0])
        return str(first)
    return str(parameter)


def _render_reference(ref, ctx):
    """Render a reference to HTML.

    Each reference output ends with a newline so that consecutive
    references get whitespace between them in flowing HTML.
    """
    topic = ref.topic
    if isinstance(topic, SageFunctionSpec):
        topic = topic.name
    topic_str = str(topic) if topic else ''
    # Strip package prefix for display (e.g. 'SCL:STRING-NCONC' -> 'STRING-NCONC')
    display_str = _strip_package_prefix(topic_str) if topic_str else ''

    appearance = ref.appearance
    booleans = ref.booleans if ref.booleans else []

    # Determine how to render based on appearance
    if appearance == 'invisible':
        return ''

    if appearance == 'topic':
        href = _resolve_href(ref, ctx)
        return f'<span class="ref-topic">\u201c<a href="{href}">{xml_escape(display_str)}</a>\u201d</span>\n'

    if appearance == 'see':
        href = _resolve_href(ref, ctx)
        type_str = _strip_package_prefix(str(ref.type)) if ref.type else ''
        cap_s = 'S' if 'initial-cap' in str(booleans) else 's'
        period = '.' if 'final-period' in str(booleans) else ''
        return f'<span class="ref-see">{cap_s}ee the {xml_escape(type_str)} <a href="{href}">{xml_escape(display_str)}</a>{period}</span>\n'

    # Default: check callee type from record
    app_lower = str(appearance).lower() if appearance else ''
    if appearance in (None, []) or app_lower in ('lisp:nil', 'common-lisp:nil'):
        callee_type = _get_callee_type(ref, ctx)

        if callee_type in ('expand', 'Expand'):
            href = _resolve_href(ref, ctx)
            return f'<div class="ref-expand"><a href="{href}">{xml_escape(display_str)}</a></div>\n'

        if callee_type == 'topic':
            href = _resolve_href(ref, ctx)
            return f'<span class="ref-topic">\u201c<a href="{href}">{xml_escape(display_str)}</a>\u201d</span>\n'

        if callee_type in ('crossreference', 'CrossRef', 'crossref'):
            href = _resolve_href(ref, ctx)
            return f'<span class="ref-crossref"><a href="{href}">{xml_escape(display_str)}</a></span>\n'

        if callee_type in ('precis', 'contents', 'operation'):
            href = _resolve_href(ref, ctx)
            return f'<span class="ref-topic">\u201c<a href="{href}">{xml_escape(display_str)}</a>\u201d</span>\n'

        # Fallback: just link
        href = _resolve_href(ref, ctx)
        return f'<a href="{href}">{xml_escape(display_str)}</a>\n'

    # Catch-all
    href = _resolve_href(ref, ctx)
    return f'<a href="{href}">{xml_escape(display_str)}</a>\n'


def _get_callee_type(ref, ctx):
    """Get the callee type for a reference from the current record."""
    if ctx.record and hasattr(ctx.record, 'callees') and ctx.record.callees:
        uid = ref.unique_id
        if uid in ctx.record.callees:
            return ctx.record.callees[uid][1]  # called_how
    return None


def _resolve_href(ref, ctx):
    """Resolve a reference to an href URL with fragment anchor."""
    if ctx.registry:
        topic = ref.topic
        if isinstance(topic, SageFunctionSpec):
            topic = topic.name
        resolved = ctx.registry.resolve_reference(ref.unique_id, topic)
        if resolved:
            relpath, target_topic, _ = resolved
            html_path = ctx.registry.get_html_path(relpath)
            anchor = _slugify(target_topic)
            # Same file? Just use fragment
            if ctx.current_file and html_path == ctx.current_file:
                return f'#{anchor}'
            if ctx.current_file:
                current_dir = os.path.dirname(ctx.current_file)
                html_path = os.path.relpath(html_path, current_dir)
            return f'{html_path}#{anchor}'
    return '#'


def _render_picture(pic, ctx=None):
    """Render a picture to HTML."""
    if not pic.contents:
        return f'<div class="picture"><p>Picture: {xml_escape(pic.name)}</p></div>'

    try:
        data = pic.contents if isinstance(pic.contents, bytes) else pic.contents.encode('latin-1')
        ops = binary_decode_graphics(data)
        link_resolver = None
        if ctx and ctx.registry:
            link_resolver = _make_svg_link_resolver(ctx)
        svg = render_picture_to_svg(ops, link_resolver=link_resolver)
        return f'<div class="picture">\n{svg}\n</div>'
    except Exception as e:
        return f'<div class="picture"><p>Picture: {xml_escape(pic.name)} (error: {xml_escape(str(e))})</p></div>'


def _make_svg_link_resolver(ctx):
    """Return a function that resolves a text string to an href, or None."""
    def resolver(text):
        # Try exact match, then upper-case match against registry by_name
        registry = ctx.registry
        for candidate in (text, text.upper(), text.lower()):
            if candidate in registry.by_name:
                info = registry.by_name[candidate]
                relpath, uid, type_sym = info
                html_path = registry.get_html_path(relpath)
                anchor = _slugify(candidate)
                if ctx.current_file and html_path == ctx.current_file:
                    return f'#{anchor}'
                if ctx.current_file:
                    current_dir = os.path.dirname(ctx.current_file)
                    html_path = os.path.relpath(html_path, current_dir)
                return f'{html_path}#{anchor}'
        return None
    return resolver


# ========== Paragraph/tab fixup (ports fix-up-special-markup) ==========

def _split_out_paragraph_markers(lst):
    """Split text items on paragraph markers, inserting _PARAGRAPH_MARKER sentinels."""
    result = []
    for item in lst:
        if isinstance(item, str) and PARAGRAPH_MARKER in item:
            parts = item.split(PARAGRAPH_MARKER)
            for i, part in enumerate(parts):
                if i > 0:
                    result.append(_PARAGRAPH_MARKER)
                if part:
                    result.append(part)
        else:
            result.append(item)
    return result


def _fix_up_tabs(lst):
    """Group content between tab-to-tab-stop commands into tab environments."""
    result = []
    this_tab = None

    for el in lst:
        if isinstance(el, SageCommand) and str(el.name) == 'tab-to-tab-stop':
            if this_tab is None:
                this_tab = []
        elif el is _PARAGRAPH_MARKER:
            if this_tab is not None:
                result.append(SageEnvr(name='nex-tab-to-tab-stop', mods=[], contents_list=list(this_tab)))
            result.append(el)
            this_tab = None
        else:
            if this_tab is not None:
                this_tab.append(el)
            else:
                result.append(el)

    if this_tab is not None:
        result.append(SageEnvr(name='nex-tab-to-tab-stop', mods=[], contents_list=list(this_tab)))

    return result


_BLOCK_ENVRS = frozenset({
    'example', 'display', 'enumerate', 'itemize', 'verbatim',
    'description', 'center', 'figure', 'group', 'multiple',
    'commentary', 'header', 'heading', 'majorheading',
    'lisp:format', 'common-lisp:format', 'global:format',
})


def _is_block_envr(el):
    """Return True if el is a SageEnvr that renders as a block-level element."""
    return isinstance(el, SageEnvr) and str(el.name) in _BLOCK_ENVRS


def _flush_paragraph(this_p, result):
    """Flush accumulated inline content as a nex-paragraph if non-empty."""
    if this_p is not None:
        filtered = [x for x in this_p if not (isinstance(x, str) and not x)]
        if filtered:
            result.append(SageEnvr(name='nex-paragraph', mods=[], contents_list=filtered))


def _fix_up_paragraphs(lst):
    """Group content between paragraph markers into paragraph environments."""
    if _PARAGRAPH_MARKER not in lst:
        return lst

    result = []
    this_p = None

    for el in lst:
        if el is _PARAGRAPH_MARKER:
            _flush_paragraph(this_p, result)
            this_p = None
        elif _is_block_envr(el):
            _flush_paragraph(this_p, result)
            this_p = None
            result.append(el)
        else:
            if this_p is None:
                this_p = []
            this_p.append(el)

    _flush_paragraph(this_p, result)

    return result


def _fix_up_special_markup(lst):
    """Apply paragraph and tab fixup to a content list."""
    return _fix_up_paragraphs(_fix_up_tabs(_split_out_paragraph_markers(lst)))


import os
