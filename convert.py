#!/usr/bin/env python3
"""CLI entry point for SAB to HTML converter."""

import argparse
import sys
import os

# Add parent dir to path so we can import sab2html
sys.path.insert(0, os.path.dirname(__file__))

from sab2html.sab_reader import read_sab
from sab2html.xml_emitter import emit_xml
from sab2html.html_renderer import render_records_to_html
from sab2html.site_generator import generate_site


def main():
    parser = argparse.ArgumentParser(
        description='Convert Symbolics Genera SAB documentation to HTML'
    )
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # 'site' command - batch convert all files
    site_parser = subparsers.add_parser('site', help='Generate complete HTML site')
    site_parser.add_argument('sab_dir', help='Directory containing SAB files')
    site_parser.add_argument('-o', '--output', default='output',
                             help='Output directory (default: output)')
    site_parser.add_argument('--xml', action='store_true',
                             help='Also emit XML files')

    # 'single' command - convert a single file
    single_parser = subparsers.add_parser('single', help='Convert a single SAB file')
    single_parser.add_argument('file', help='SAB file to convert')
    single_parser.add_argument('-o', '--output', help='Output file (default: stdout)')
    single_parser.add_argument('--format', choices=['html', 'xml'], default='html',
                               help='Output format (default: html)')

    # 'info' command - show file info
    info_parser = subparsers.add_parser('info', help='Show SAB file info')
    info_parser.add_argument('file', help='SAB file to inspect')

    args = parser.parse_args()

    if args.command == 'site':
        generate_site(args.sab_dir, args.output, emit_xml_files=args.xml)

    elif args.command == 'single':
        attrs, records, index = read_sab(args.file)
        title = ''
        for r in records:
            if hasattr(r, 'name'):
                from sab2html.sab_types import SageFunctionSpec
                title = r.name.name if isinstance(r.name, SageFunctionSpec) else str(r.name)
                break

        if args.format == 'xml':
            output = emit_xml(attrs, records, index, source_path=args.file)
        else:
            output = render_records_to_html(records, index, title=title)
            output = output.replace('{{CSS_PATH}}', 'style.css')
            output = output.replace('{{INDEX_PATH}}', 'index.html')

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f"Written to {args.output}")
        else:
            print(output)

    elif args.command == 'info':
        attrs, records, index = read_sab(args.file)
        print(f"File: {args.file}")
        print(f"Records: {len(records)}")
        print(f"Index items: {len(index)}")
        if isinstance(attrs, list):
            print("Attributes:")
            for item in attrs:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    print(f"  {item[0]}: {item[1]}")
        print("Records:")
        for r in records:
            if hasattr(r, 'name'):
                from sab2html.sab_types import SageFunctionSpec
                name = r.name.name if isinstance(r.name, SageFunctionSpec) else str(r.name)
                print(f"  {name} ({r.type})")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
