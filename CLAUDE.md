# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

All commands use the project venv: `source venv/bin/activate` or prefix with `./venv/bin/python3`.

```bash
# Generate complete HTML site from SAB files (main workflow)
python3 convert.py site /opt/symbolics/lib/rel-9-0/sys.sct -o output

# Also emit XML intermediate files
python3 convert.py site /opt/symbolics/lib/rel-9-0/sys.sct -o output --xml

# Convert a single SAB file
python3 convert.py single FILE.sab --format html
python3 convert.py single FILE.sab --format xml

# Inspect a SAB file's structure
python3 convert.py info FILE.sab

# Serve the generated site locally
cd output && python3 -m http.server 8000

# Take headless screenshots for visual verification
chromium --headless --no-sandbox --disable-gpu --screenshot=/tmp/page.png --window-size=1200,3000 "file:///home/hans/symbolics-docs/output/path/to/file.html"
```

There are no tests.

## Architecture

Converts Symbolics Genera SAB (Sage Abstract Browser) binary documentation into browsable HTML. Ported from [ecraven/sab-files](https://github.com/ecraven/sab-files) (MIT Scheme).

### Two-Pass Pipeline

**Pass 1** (`cross_references.py`): Fast index-only scan of all SAB files via `read_sab_index_only()`. Builds a global `RecordRegistry` with three lookup maps (`by_id`, `by_index`, `by_name`) so cross-file references can be resolved.

**Pass 2** (`site_generator.py`): Full parse of each SAB file, then renders HTML (and optionally XML). The registry from Pass 1 is threaded through rendering for link resolution.

### Data Flow

```
SAB binary → sab_reader.py (46 type codes, dispatch table)
           → Parsed AST (SageRecord, SageEnvr, SageCommand, SageReference, SagePicture)
           → html_renderer.py (60+ environments, 30+ commands)
           → HTML pages with cross-references, inline SVG, search index
```

### Key Modules

- **`sab_reader.py`**: Dispatch-table parser. Each of 46 SAB type codes has a registered reader function. Uses `SabStream` (from `stream.py`) for binary I/O and `SymbolTable` (from `sab_types.py`) for symbol accumulation. A fresh symbol table is created per record.
- **`genera_charset.py`**: Maps Genera's character encoding to Unicode. Bytes 0x00-0x1F are special characters (Greek, math). Byte 0x8D is paragraph/line break marker. Byte 0x89 is a tab character expanded to spaces at 8-column stops. Bytes 0x7F-0x9F (except 0x89, 0x8D) are C1 controls that get stripped.
- **`html_renderer.py`**: Core rendering. `_render_sage()` dispatches on AST type. `_render_envr()` handles 60+ environment types. `_fix_up_special_markup()` converts paragraph markers and tab-to-tab-stop commands into proper HTML structure. Records are classified as structural (section/chapter) or entry types, with entry types getting indented body formatting.
- **`cross_references.py`**: `RecordRegistry` resolves references across files. `_resolve_href()` in the renderer uses it to generate relative paths with `#fragment` anchors.
- **`binary_graphics.py`** + **`svg_renderer.py`**: Decode a binary graphics sub-format (vector drawing ops) into SVG. Text elements in SVGs can be linked to documented symbols via a `link_resolver` callback.
- **`site_generator.py`**: Orchestrates batch conversion. Generates index page with category grouping, search page, and a JSON search index.

### HTML Rendering Patterns

- Paragraph/line break markers use Unicode Private Use Area sentinels (`\ue000`, `\ue001`) throughout the pipeline
- `_fix_up_special_markup()` transforms flat content lists into nested paragraph/tab-stop structures before rendering
- `LINE_BREAK_MARKER` renders as `\n` (collapses to space in flowing HTML, preserves breaks in `<pre>`)
- Record anchors use `_slugify()` for URL-safe IDs
- CSS path placeholders (`{{CSS_PATH}}`, `{{INDEX_PATH}}`) are replaced based on output file depth

## Semantic Search

Uses a separate venv with PyTorch + sentence-transformers (~2.3GB disk, CPU-only):

```bash
# One-time setup
python3 -m venv venv-search
./venv-search/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
./venv-search/bin/pip install sentence-transformers fastapi uvicorn[standard]

# Build embedding index from XML (requires --xml output, ~15-25 min on CPU)
./venv-search/bin/python3 build_embeddings.py output

# Run search server (serves site + semantic/keyword/hybrid search API)
./venv-search/bin/python3 search_server.py --output output --port 8000
```

- **`build_embeddings.py`**: Extracts text from `output/**/*.xml`, chunks, embeds with `BAAI/bge-large-en-v1.5`, saves to `output/semantic-index/`
- **`search_server.py`**: FastAPI app with `/api/search?q=...&mode=semantic|keyword|hybrid` and `/api/status`. Mounts `output/` as static files.
- **`static/search-semantic.js`**: Client-side code that probes the API; falls back to keyword-only search.js if server is unavailable.

## SAB Source Location

The Genera 9.0 SAB files are at `/opt/symbolics/lib/rel-9-0/sys.sct`. The build produces 851 HTML files in ~13 seconds.
