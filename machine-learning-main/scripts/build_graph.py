"""Build a simple knowledge graph from enriched_syntax.jsonl.

Outputs:
- data/knowledge_graph.json (nodes, links)
- copies to api/static/graph.json for the frontend UI

Edges are created by co-occurrence: words mentioned in the example sentence
are linked to the main entry word. If spaCy `nlp` is available, it will be
used to extract lemmas and nouns; otherwise a simple tokenization is used.
"""
import json
from pathlib import Path
from collections import defaultdict

try:
    from services.services import nlp, db
except Exception:
    nlp = None
    db = None

DATA_DIR = Path(__file__).parent.parent / "data"
ENRICHED_SYNTAX = DATA_DIR / "enriched_syntax.jsonl"
OUT_JSON = DATA_DIR / "knowledge_graph.json"
STATIC_JSON = Path(__file__).parent / "api" / "static" / "graph.json"
STATIC_JSON.parent.mkdir(parents=True, exist_ok=True)


def extract_terms(text):
    if not text:
        return []
    if nlp:
        doc = nlp(text)
        terms = [tok.lemma_.lower() for tok in doc if tok.pos_ in ("NOUN", "PROPN", "VERB", "ADJ")]
        return list(dict.fromkeys(terms))
    # fallback simple tokenization
    tokens = [w.strip(".,!?;()\"'`).:[]") for w in text.lower().split()]
    tokens = [t for t in tokens if len(t) > 2]
    return list(dict.fromkeys(tokens))


def build_graph():
    if not ENRICHED_SYNTAX.exists():
        print(f"No enriched_syntax.jsonl found at {ENRICHED_SYNTAX}. Run enrichment and parsing first.")
        return

    nodes = {}
    links_counter = defaultdict(int)

    with ENRICHED_SYNTAX.open('r', encoding='utf-8') as f:
        for line in f:
            try:
                entry = json.loads(line)
            except Exception:
                continue
            word = entry.get('word')
            if not word:
                continue
            word_norm = word.lower()
            if word_norm not in nodes:
                nodes[word_norm] = {"id": word_norm, "label": word_norm, "category": entry.get('category', 'unknown')}

            # find terms in example and in definition
            example = entry.get('example') or ''
            definition = entry.get('definition') or ''
            terms = extract_terms(example) + extract_terms(definition)
            for t in terms:
                if t == word_norm:
                    continue
                links_counter[(word_norm, t)] += 1
                # ensure node exists for t
                if t not in nodes:
                    nodes[t] = {"id": t, "label": t, "category": 'derived'}

    # build links list
    links = []
    for (a, b), w in links_counter.items():
        links.append({"source": a, "target": b, "weight": w})

    graph = {"nodes": list(nodes.values()), "links": links}

    # write outputs
    with OUT_JSON.open('w', encoding='utf-8') as f:
        json.dump(graph, f, indent=2)

    # copy to static
    try:
        with STATIC_JSON.open('w', encoding='utf-8') as f:
            json.dump(graph, f)
    except Exception:
        pass

    print(f"Wrote knowledge graph: {OUT_JSON}")

    # optionally persist nodes/edges to Firestore (best-effort)
    if db:
        try:
            coll = db.collection('knowledge_graph')
            # overwrite a single doc
            coll.document('graph').set(graph)
            print("Persisted graph to Firestore collection 'knowledge_graph' (document 'graph').")
        except Exception as e:
            print(f"Failed to persist to Firestore: {e}")

    # Optionally write to Neo4j when requested via env
    try:
        import os
        if os.environ.get('USE_NEO4J') in ('1', 'true', 'True'):
            try:
                from services.neo4j_helper import bulk_write
                print('Writing graph to Neo4j...')
                # prepare nodes/links in expected shape
                nodes_payload = []
                for n in graph['nodes']:
                    nodes_payload.append({
                        'id': n.get('id'),
                        'label': n.get('label'),
                        'category': n.get('category'),
                        'definition': n.get('definition', '')
                    })
                links_payload = []
                for l in graph['links']:
                    links_payload.append({
                        'source': l.get('source'),
                        'target': l.get('target'),
                        'weight': l.get('weight', 1),
                        'source_name': 'build_graph'
                    })
                bulk_write(nodes_payload, links_payload)
                print('Neo4j import complete.')
            except Exception as e:
                print(f'Neo4j write failed: {e}')
    except Exception:
        pass


if __name__ == '__main__':
    build_graph()
