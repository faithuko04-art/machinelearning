#!/usr/bin/env python3
"""Import an existing data/knowledge_graph.json into Neo4j.

Usage:
    python scripts/import_to_neo4j.py --file data/knowledge_graph.json --create-index
"""
import json
from pathlib import Path
import argparse


def main():
    parser = argparse.ArgumentParser(description='Import knowledge_graph.json into Neo4j')
    parser.add_argument('--file', '-f', default='data/knowledge_graph.json')
    parser.add_argument('--create-index', action='store_true', help='Create index on Concept.id')
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"Graph file not found: {path}")
        return 2

    try:
        from services.neo4j_helper import bulk_write, driver
    except Exception as e:
        print(f"Neo4j helper not available: {e}")
        return 3

    with path.open('r', encoding='utf-8') as f:
        graph = json.load(f)

    nodes = []
    for n in graph.get('nodes', []):
        nodes.append({
            'id': n.get('id'),
            'label': n.get('label') or n.get('id'),
            'category': n.get('category', 'unknown'),
            'definition': n.get('definition', '')
        })

    links = []
    for l in graph.get('links', []):
        links.append({
            'source': l.get('source'),
            'target': l.get('target'),
            'weight': l.get('weight', 1),
            'source_name': 'import'
        })

    if args.create_index:
        try:
            drv = driver()
            with drv.session() as sess:
                print('Creating index on :Concept(id) if not exists...')
                sess.run("CREATE INDEX concept_id_index IF NOT EXISTS FOR (c:Concept) ON (c.id)")
        except Exception as e:
            print(f'Failed to create index: {e}')

    print(f'Importing {len(nodes)} nodes and {len(links)} links to Neo4j...')
    try:
        bulk_write(nodes, links)
        print('Import complete.')
    except Exception as e:
        print(f'Import failed: {e}')
        return 4

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
