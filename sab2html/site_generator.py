"""Batch processing, index generation, and search index for the static site."""

import json
import os
import shutil
import sys
import time

from .sab_reader import read_sab
from .sab_types import SageRecord, SageFunctionSpec
from .xml_emitter import emit_xml
from .html_renderer import render_records_to_html
from .cross_references import RecordRegistry
from xml.sax.saxutils import escape as xml_escape


def generate_site(sab_dir: str, output_dir: str, emit_xml_files=False):
    """Generate the complete static site from SAB files.

    Args:
        sab_dir: Root directory containing SAB files
        output_dir: Output directory for generated HTML
        emit_xml_files: If True, also emit XML files alongside HTML
    """
    print(f"Scanning SAB files in {sab_dir}...")
    t0 = time.time()

    # Pass 1: Build cross-reference registry
    registry = RecordRegistry()
    file_count = registry.scan_all(sab_dir)
    t1 = time.time()
    print(f"  Scanned {file_count} files in {t1 - t0:.1f}s")
    print(f"  {len(registry.by_id)} unique IDs, {len(registry.by_index)} numeric indices")

    # Collect all SAB file paths
    sab_files = []
    for root, dirs, fnames in os.walk(sab_dir):
        for fn in fnames:
            if '.sab.' in fn:
                sab_files.append(os.path.join(root, fn))
    sab_files.sort()

    # Setup output directory
    os.makedirs(output_dir, exist_ok=True)

    # Copy static files
    static_src = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    if os.path.isdir(static_src):
        for fn in os.listdir(static_src):
            shutil.copy2(os.path.join(static_src, fn), os.path.join(output_dir, fn))

    # Pass 2: Convert each file
    print(f"Converting {len(sab_files)} files...")
    t2 = time.time()
    ok = 0
    fail = 0
    search_entries = []
    file_index = {}  # category -> [(title, relpath, type)]

    for filepath in sab_files:
        relpath = os.path.relpath(filepath, sab_dir)
        html_relpath = registry.get_html_path(relpath)

        try:
            attrs, records, index = read_sab(filepath)

            # Get page title
            page_title = _get_page_title(records)

            # Generate HTML
            html = render_records_to_html(
                records, index,
                registry=registry,
                current_file=html_relpath,
                title=page_title,
                file_attrs=attrs,
            )

            # Fix up CSS/index paths based on output directory depth
            depth = html_relpath.count('/')
            prefix = '../' * depth if depth > 0 else ''
            html = html.replace('{{CSS_PATH}}', prefix + 'style.css')
            html = html.replace('{{INDEX_PATH}}', prefix + 'index.html')

            # Write HTML
            out_path = os.path.join(output_dir, html_relpath)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(html)

            # Optionally write XML
            if emit_xml_files:
                xml = emit_xml(attrs, records, index, source_path=relpath)
                xml_path = out_path.replace('.html', '.xml')
                with open(xml_path, 'w', encoding='utf-8') as f:
                    f.write(xml)

            # Build search index entries
            for record in records:
                if isinstance(record, SageRecord):
                    name = record.name
                    if isinstance(name, SageFunctionSpec):
                        name = name.name
                    text = _extract_text(record)
                    search_entries.append({
                        'title': str(name),
                        'type': str(record.type),
                        'path': html_relpath,
                        'file': relpath,
                        'text': text[:300],
                    })

            # Categorize for index
            category = _categorize(relpath)
            if category not in file_index:
                file_index[category] = []
            file_index[category].append((page_title, html_relpath, relpath))

            ok += 1
            if ok % 100 == 0:
                print(f"  {ok}/{len(sab_files)}...")

        except Exception as e:
            fail += 1
            print(f"  FAIL: {relpath} - {type(e).__name__}: {e}", file=sys.stderr)

    t3 = time.time()
    print(f"  Converted {ok} files ({fail} failures) in {t3 - t2:.1f}s")

    # Write search index
    search_path = os.path.join(output_dir, 'search-index.json')
    with open(search_path, 'w', encoding='utf-8') as f:
        json.dump(search_entries, f, ensure_ascii=False)
    print(f"  Search index: {len(search_entries)} entries")

    # Generate index page
    index_html = _generate_index_page(file_index, ok, fail, t3 - t0)
    with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index_html)

    # Generate search page
    search_html = _generate_search_page()
    with open(os.path.join(output_dir, 'search.html'), 'w', encoding='utf-8') as f:
        f.write(search_html)

    print(f"Done! Total time: {t3 - t0:.1f}s")
    print(f"Output: {output_dir}/")


def _get_page_title(records):
    """Get a page title from the first record."""
    for r in records:
        if isinstance(r, SageRecord):
            name = r.name
            if isinstance(name, SageFunctionSpec):
                return name.name
            return str(name)
    return "Untitled"


def _extract_text(record):
    """Extract plain text from a record for search indexing."""
    texts = []
    _collect_text(record, texts)
    return ' '.join(texts)


def _collect_text(obj, texts):
    """Recursively collect text strings from SAB objects."""
    if isinstance(obj, str):
        # Strip markers
        from .genera_charset import PARAGRAPH_MARKER, LINE_BREAK_MARKER
        clean = obj.replace(PARAGRAPH_MARKER, ' ').replace(LINE_BREAK_MARKER, ' ')
        if clean.strip():
            texts.append(clean.strip())
    elif isinstance(obj, SageRecord):
        for fname, fval in obj.fields:
            if fname == 'contents':
                _collect_text(fval, texts)
    elif isinstance(obj, list):
        for item in obj:
            _collect_text(item, texts)
    elif hasattr(obj, 'contents_list'):
        for item in obj.contents_list:
            _collect_text(item, texts)
    elif hasattr(obj, 'parameter') and obj.parameter:
        _collect_text(obj.parameter, texts)


def _categorize(relpath: str) -> str:
    """Categorize a file path into a documentation section."""
    parts = relpath.split('/')
    if len(parts) >= 2:
        top = parts[0]
        if top == 'doc':
            # doc/installed-442/category/file or doc/clim/file or doc/file.sab
            if len(parts) >= 4 and parts[1] == 'installed-442':
                return f"doc/{parts[2]}"
            elif len(parts) >= 3 and not parts[1].endswith('.sab'):
                return f"doc/{parts[1]}"
            else:
                return "doc/misc"
        return top
    return "other"


# Category display names
CATEGORY_NAMES = {
    'doc/user': 'User Documentation',
    'doc/cl': 'Common Lisp',
    'doc/ansi-cl': 'ANSI Common Lisp',
    'doc/zmacs': 'Zmacs Editor',
    'doc/zmail': 'ZMail',
    'doc/zmailt': 'ZMail (Tutorial)',
    'doc/zmailc': 'ZMail (Commands)',
    'doc/windoc': 'Window System',
    'doc/menus': 'Menus',
    'doc/debug': 'Debugger',
    'doc/comp': 'Compiler',
    'doc/eval': 'Evaluator',
    'doc/proc': 'Processes',
    'doc/file': 'File System',
    'doc/io': 'Input/Output',
    'doc/netio': 'Network I/O',
    'doc/nfile': 'Network File System',
    'doc/rpc': 'RPC',
    'doc/ip-tcp': 'IP/TCP',
    'doc/maint': 'Maintenance',
    'doc/site': 'Site Management',
    'doc/sig': 'System Installation',
    'doc/stor': 'Storage',
    'doc/sched': 'Scheduler',
    'doc/prim': 'Primitives',
    'doc/func': 'Functions',
    'doc/data-types': 'Data Types',
    'doc/flow': 'Flow Control',
    'doc/strings': 'Strings',
    'doc/pkg': 'Packages',
    'doc/clos': 'CLOS',
    'doc/flav': 'Flavors',
    'doc/defs': 'Definitions',
    'doc/hard': 'Hardware',
    'doc/int': 'Internals',
    'doc/tools': 'Tools',
    'doc/conv': 'Conversion',
    'doc/fed': 'FED',
    'doc/fep': 'FEP',
    'doc/scroll': 'Scroll',
    'doc/uims': 'UIMS',
    'doc/macivory': 'MacIvory',
    'doc/ux400': 'UX400/UX1200',
    'doc/ivory': 'Ivory',
    'doc/vlm': 'Virtual Lisp Machine',
    'c/doc': 'C Language',
    'pascal/doc': 'Pascal',
    'fortran/doc': 'Fortran',
    'concordia/doc': 'Concordia',
    'graphic-editor': 'Graphic Editor',
    'joshua/doc': 'Joshua',
    'statice/documentation': 'Statice',
    'color/doc': 'Color',
    'doc/clim': 'CLIM',
    'doc/rn8-0': 'Release Notes 8.0',
    'doc/rn8-0-1': 'Release Notes 8.0.1',
    'doc/rn8-1': 'Release Notes 8.1',
    'doc/rn8-1-eco': 'Release Notes 8.1 ECO',
    'doc/rn8-2': 'Release Notes 8.2',
    'doc/rn8-3': 'Release Notes 8.3',
    'doc/rn-poly': 'Release Notes (Poly)',
    'doc/cp': 'Command Processor',
    'doc/init': 'Initialization',
    'doc/lms': 'Lisp Machine System',
    'doc/tape': 'Tape',
    'doc/sage': 'Sage',
    'doc/scope': 'Scope',
    'doc/meter': 'Metering',
    'doc/meter-int': 'Metering (Internal)',
    'doc/nota': 'Notation',
    'doc/conv': 'Conversion',
    'doc/conversion': 'Conversion Utilities',
    'doc/conversion-tools': 'Conversion Tools',
    'doc/char': 'Characters',
    'doc/str': 'Structures',
    'doc/cond': 'Conditions',
    'doc/mac': 'Macros',
    'doc/iprim': 'Internal Primitives',
    'doc/pig': 'PIG',
    'doc/prot': 'Protocol',
    'doc/fsed': 'FSED',
    'doc/ined': 'INED',
    'doc/arr': 'Arrays',
    'doc/misct': 'Miscellaneous (Topics)',
    'doc/miscf': 'Miscellaneous (Functions)',
    'doc/miscu': 'Miscellaneous (User)',
    'doc/miscui': 'Miscellaneous (UI)',
    'doc/intstr': 'Internal Structures',
    'doc/workstyles': 'Workstyles',
    'doc/audio': 'Audio',
    'doc/clyde': 'Clyde',
    'doc/misc': 'Miscellaneous Documentation',
    'doc/installed-442': 'Documentation',
    'contributed': 'Contributed',
    'ip-tcp': 'IP/TCP',
    'nfs': 'NFS',
    'x11': 'X11',
}


def _generate_index_page(file_index, ok, fail, elapsed):
    """Generate the main index.html page."""
    sections = []

    # Sort categories
    sorted_cats = sorted(file_index.keys(),
                         key=lambda c: CATEGORY_NAMES.get(c, c).lower())

    for category in sorted_cats:
        files = sorted(file_index[category], key=lambda f: f[0].lower())
        display_name = CATEGORY_NAMES.get(category, category)

        items = []
        for title, html_path, sab_path in files:
            items.append(f'        <li><a href="{html_path}">{xml_escape(title)}</a></li>')

        sections.append(
            f'    <div class="index-section">\n'
            f'      <h2>{xml_escape(display_name)} ({len(files)})</h2>\n'
            f'      <ul>\n' +
            '\n'.join(items) +
            f'\n      </ul>\n'
            f'    </div>'
        )

    sections_html = '\n'.join(sections)
    return (
        f'<!DOCTYPE html>\n'
        f'<html lang="en">\n'
        f'<head>\n'
        f'  <meta charset="utf-8">\n'
        f'  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'  <title>Symbolics Genera Documentation</title>\n'
        f'  <link rel="stylesheet" href="style.css">\n'
        f'</head>\n'
        f'<body>\n'
        f'<h1>Symbolics Genera Documentation</h1>\n'
        f'<p>Converted from {ok + fail} SAB files from Genera 9.0 / Open Genera.</p>\n'
        f'<p><a href="search.html">Search documentation</a></p>\n'
        f'<p class="stats">{ok} files converted, {fail} errors, {elapsed:.1f}s total</p>\n'
        f'{sections_html}\n'
        f'</body>\n'
        f'</html>\n'
    )


def _generate_search_page():
    """Generate the search.html page."""
    return (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '  <title>Search - Symbolics Genera Documentation</title>\n'
        '  <link rel="stylesheet" href="style.css">\n'
        '</head>\n'
        '<body>\n'
        '<nav class="breadcrumb"><a href="index.html">Index</a></nav>\n'
        '<h1>Search Documentation</h1>\n'
        '<div class="search-box">\n'
        '  <input type="text" id="search-input" placeholder="Search..." autofocus>\n'
        '  <div class="search-controls">\n'
        '    <select id="search-mode" disabled>\n'
        '      <option value="hybrid">Hybrid</option>\n'
        '      <option value="semantic">Semantic</option>\n'
        '      <option value="keyword">Keyword</option>\n'
        '    </select>\n'
        '    <span id="server-status" class="server-status status-off">Checking server...</span>\n'
        '  </div>\n'
        '</div>\n'
        '<ul id="search-results" class="search-results"></ul>\n'
        '<script src="search.js"></script>\n'
        '<script src="search-semantic.js"></script>\n'
        '</body>\n'
        '</html>\n'
    )
