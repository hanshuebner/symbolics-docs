#!/usr/bin/env python3
"""Build semantic search embeddings from XML documentation files.

Walks output/**/*.xml, extracts text from <record> elements,
chunks long entries, embeds with bge-large-en-v1.5, and saves
to output/semantic-index/.

Usage:
    ./venv-search/bin/python3 build_embeddings.py output
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


def extract_records(xml_path, output_dir):
    """Extract records from an XML file.

    Returns list of dicts with keys: name, type, unique_id, text, html_path.
    """
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        return []

    root = tree.getroot()
    rel_xml = os.path.relpath(xml_path, output_dir)
    html_path = rel_xml.rsplit('.xml', 1)[0] + '.html'

    records = []
    for record_el in root.iter('record'):
        name = record_el.get('name', '')
        rec_type = record_el.get('type', '')
        unique_id = record_el.get('unique-id', '')

        # Collect text from the contents field
        texts = []
        for field_el in record_el.findall('field'):
            if field_el.get('name') == 'contents':
                for text_el in field_el.iter('text'):
                    if text_el.text:
                        texts.append(text_el.text.strip())

        body = ' '.join(texts)
        if not body and not name:
            continue

        records.append({
            'name': name,
            'type': rec_type,
            'unique_id': unique_id,
            'text': body,
            'html_path': html_path,
        })

    return records


def chunk_text(text, max_chars=1500, overlap=200):
    """Split text at paragraph boundaries with overlap.

    Returns list of text chunks. Most entries are short enough
    to be a single chunk.
    """
    if len(text) <= max_chars:
        return [text]

    # Split on double-space or sentence boundaries
    paragraphs = text.split('  ')
    if len(paragraphs) == 1:
        # No paragraph breaks; split on sentences
        paragraphs = []
        remaining = text
        while len(remaining) > max_chars:
            # Find last sentence end within max_chars
            cut = remaining[:max_chars].rfind('. ')
            if cut < max_chars // 3:
                cut = max_chars  # Force cut if no good boundary
            else:
                cut += 2  # Include the period and space
            paragraphs.append(remaining[:cut])
            remaining = remaining[max(0, cut - overlap):]
        if remaining:
            paragraphs.append(remaining)
        return paragraphs

    # Reassemble paragraphs into chunks
    chunks = []
    current = ''
    for para in paragraphs:
        if len(current) + len(para) + 2 > max_chars and current:
            chunks.append(current)
            # Overlap: keep the tail of the current chunk
            if overlap > 0 and len(current) > overlap:
                current = current[-overlap:] + '  ' + para
            else:
                current = para
        else:
            current = current + '  ' + para if current else para
    if current:
        chunks.append(current)

    return chunks


def build_entries(output_dir):
    """Walk all XML files and build chunk entries for embedding."""
    entries = []
    xml_files = []

    for dirpath, _dirs, filenames in os.walk(output_dir):
        for fn in filenames:
            if fn.endswith('.xml'):
                xml_files.append(os.path.join(dirpath, fn))

    xml_files.sort()
    print(f"Found {len(xml_files)} XML files")

    for xml_path in tqdm(xml_files, desc="Extracting records"):
        records = extract_records(xml_path, output_dir)
        for rec in records:
            # Build embedding text: prepend type + name for context
            prefix = ''
            if rec['type']:
                prefix = rec['type'].upper()
            if rec['name']:
                prefix = f"{prefix}: {rec['name']}" if prefix else rec['name']

            body = rec['text']
            if not body:
                # Even records with no body text are worth indexing by name
                if prefix:
                    entries.append({
                        'embed_text': prefix,
                        'name': rec['name'],
                        'type': rec['type'],
                        'unique_id': rec['unique_id'],
                        'html_path': rec['html_path'],
                        'chunk_index': 0,
                        'total_chunks': 1,
                    })
                continue

            chunks = chunk_text(body)
            for i, chunk in enumerate(chunks):
                embed_text = f"{prefix} -- {chunk}" if prefix else chunk
                entries.append({
                    'embed_text': embed_text,
                    'name': rec['name'],
                    'type': rec['type'],
                    'unique_id': rec['unique_id'],
                    'html_path': rec['html_path'],
                    'chunk_index': i,
                    'total_chunks': len(chunks),
                })

    return entries


def main():
    parser = argparse.ArgumentParser(description='Build semantic search embeddings')
    parser.add_argument('output_dir', help='Output directory containing XML files')
    parser.add_argument('--model', default='BAAI/bge-large-en-v1.5',
                        help='Sentence transformer model name')
    parser.add_argument('--batch-size', type=int, default=32,
                        help='Embedding batch size')
    args = parser.parse_args()

    output_dir = args.output_dir
    if not os.path.isdir(output_dir):
        print(f"Error: {output_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    # Step 1: Extract and chunk
    print("Step 1: Extracting records from XML files...")
    entries = build_entries(output_dir)
    print(f"  {len(entries)} chunks to embed")

    if not entries:
        print("No entries found. Did you generate XML with --xml?", file=sys.stderr)
        sys.exit(1)

    # Step 2: Load model and embed
    print(f"Step 2: Loading model {args.model}...")
    model = SentenceTransformer(args.model)

    print(f"Step 3: Embedding {len(entries)} chunks (batch_size={args.batch_size})...")
    texts = [e['embed_text'] for e in entries]
    embeddings = model.encode(
        texts,
        batch_size=args.batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    # Step 3: Save
    index_dir = os.path.join(output_dir, 'semantic-index')
    os.makedirs(index_dir, exist_ok=True)

    # Save embeddings as float16 to save space
    emb_path = os.path.join(index_dir, 'embeddings.npz')
    np.savez_compressed(emb_path, embeddings=embeddings.astype(np.float16))
    emb_size = os.path.getsize(emb_path) / (1024 * 1024)
    print(f"  Saved embeddings to {emb_path} ({emb_size:.1f} MB)")

    # Save chunk metadata (everything except embed_text)
    chunks_meta = []
    for e in entries:
        chunks_meta.append({
            'name': e['name'],
            'type': e['type'],
            'unique_id': e['unique_id'],
            'html_path': e['html_path'],
            'chunk_index': e['chunk_index'],
            'total_chunks': e['total_chunks'],
        })

    chunks_path = os.path.join(index_dir, 'chunks.json')
    with open(chunks_path, 'w', encoding='utf-8') as f:
        json.dump(chunks_meta, f, ensure_ascii=False)
    chunks_size = os.path.getsize(chunks_path) / (1024 * 1024)
    print(f"  Saved metadata to {chunks_path} ({chunks_size:.1f} MB)")

    print("Done!")


if __name__ == '__main__':
    main()
