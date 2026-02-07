"""Run spaCy POS tagging and dependency parsing on enriched examples.

Reads `data/enriched.jsonl` and appends a `syntax` field to `solidified_knowledge`
collection (Firestore) or writes a local file `data/enriched_syntax.jsonl`.
"""
import json
from pathlib import Path
try:
    from services.services import nlp, db
except Exception:
    nlp = None
    db = None

DATA_DIR = Path(__file__).parent.parent / "data"
ENRICHED = DATA_DIR / "enriched.jsonl"
OUT_FILE = DATA_DIR / "enriched_syntax.jsonl"


def parse_text(text):
    if not nlp:
        return None
    doc = nlp(text)
    tokens = [{"text": t.text, "pos": t.pos_, "tag": t.tag_, "dep": t.dep_, "head": t.head.text} for t in doc]
    sent_templates = []
    for sent in doc.sents:
        sent_templates.append({
            "text": sent.text,
            "deps": [(t.text, t.dep_, t.head.text) for t in sent]
        })
    return {"tokens": tokens, "sentences": sent_templates}


def main():
    if not ENRICHED.exists():
        print(f"No enriched file found at {ENRICHED}. Run batch_enrich first.")
        return

    with ENRICHED.open('r', encoding='utf-8') as inf, OUT_FILE.open('w', encoding='utf-8') as outf:
        for line in inf:
            try:
                entry = json.loads(line)
            except Exception:
                continue
            example = entry.get('example') or ''
            syntax = parse_text(example) if example else None
            entry['syntax'] = syntax

            # write local output
            outf.write(json.dumps(entry) + '\n')

            # persist to Firestore
            try:
                if db:
                    doc = db.collection('solidified_knowledge').document(entry['word'])
                    doc.set({'enrichment': entry, 'syntax': syntax}, merge=True)
            except Exception:
                pass

    print(f"Syntax parsing complete. Output: {OUT_FILE}")


if __name__ == '__main__':
    main()
