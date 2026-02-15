# sab2html - Symbolics Genera SAB to XML/HTML Converter

Converts Symbolics Genera SAB (Sage Abstract Browser) binary documentation files to semantic XML and browsable HTML. These are the hypertext documentation files from the Genera Document Examiner / Concordia system.

## Architecture

```
SAB binary files
      |
      v
  [sab2html parser]        -- binary parsing (46 type codes, graphics sub-format)
      |
      v
  Semantic XML (.xml)       -- lossless intermediate representation
      |
      v
  [HTML renderer]           -- output generation
      |
      +---> HTML static site (with client-side search)
      +---> XML files (for further processing)
```

## Usage

```bash
# Setup
python3 -m venv venv
./venv/bin/pip install lxml Pillow

# Generate complete site from all SAB files
./venv/bin/python3 convert.py site /path/to/sys.sct -o output --xml

# Convert a single file
./venv/bin/python3 convert.py single FILE.sab --format html
./venv/bin/python3 convert.py single FILE.sab --format xml

# Inspect a file
./venv/bin/python3 convert.py info FILE.sab

# Serve the generated site
cd output && python3 -m http.server
```

## Project Structure

```
sab2html/
    stream.py             # Binary stream reader (SabStream class)
    sab_types.py          # 46 SAB type code constants + dataclasses
    sab_reader.py         # SAB parser: dispatch table, all 46 readers
    binary_graphics.py    # Binary graphics sub-format (15 commands, 16 operations)
    genera_charset.py     # Genera character encoding -> Unicode mapping
    sexpr_parser.py       # Minimal S-expression parser (for read-from-string)
    xml_emitter.py        # Parsed AST -> semantic XML output
    cross_references.py   # Global record registry, two-pass processing
    html_renderer.py      # SAB structures -> HTML (60+ environments, 30+ commands)
    svg_renderer.py       # Graphics operations -> SVG strings
    png_writer.py         # Raster images -> PNG (via Pillow, with bit-flip)
    site_generator.py     # Batch processing, index, search index
convert.py                # CLI entry point
static/
    style.css             # Site stylesheet
    search.js             # Client-side search
```

## SAB Format

SAB files are binary compiled documentation from the Symbolics Concordia system. Each file contains:

- A header with magic number (0x00000000) and version (7)
- File attributes (compilation user, machine, time, pathnames)
- Records section: document content with nested environments, commands, references, and pictures
- Index section: metadata for each record including unique IDs, tokens, and callee lists

The parser handles 46 type codes, Genera-specific character encoding (Greek letters, math symbols, arrows), and a binary graphics sub-format with 16 drawing operations (lines, rectangles, ellipses, bezier curves, paths, raster images, etc.).

## Output

For the Genera 9.0 distribution (851 SAB files, ~52MB):

- 851 HTML files + index + search page
- 851 XML files (with `--xml` flag)
- 17,671 search index entries
- Cross-references resolved across files (17,401 unique IDs, 12,188 numeric indices)
- Inline SVG for vector graphics, base64 PNG for raster images
- Full site generation in ~20 seconds

## Credits

Ported from the MIT Scheme implementation by [ecraven/sab-files](https://github.com/ecraven/sab-files).
