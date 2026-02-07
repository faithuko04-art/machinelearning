"""Batch enrich candidate words using Groq (or fallback) and store results.

Writes per-word JSON lines to `data/enriched.jsonl` and optionally to Firestore
collections `known_words` and `solidified_knowledge` when Firestore is configured.
"""
import json
import os
from pathlib import Path
from time import sleep
try:
    from services.ai_providers import groq_generate_text
    from services.services import groq_client, db
except Exception:
    groq_generate_text = None
    groq_client = None
    db = None

try:
    from brain.db import add_word
except Exception:
    def add_word(word, explanation, is_known=False, category=None):
        return None

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CANDIDATES_FILE = DATA_DIR / "candidates.json"
OUT_FILE = DATA_DIR / "enriched.jsonl"

BATCH_SIZE = int(os.environ.get('BATCH_SIZE', 25))
DELAY_BETWEEN_BATCHES = float(os.environ.get('DELAY_BETWEEN_BATCHES', 0.5))


def load_candidates():
    if not CANDIDATES_FILE.exists():
        raise FileNotFoundError(f"Candidates file not found: {CANDIDATES_FILE}")
    with CANDIDATES_FILE.open('r', encoding='utf-8') as f:
        return json.load(f)


def enrich_batch(words):
    system = "You are an assistant that returns structured JSON for a list of words."
    user = (
        "For the following words, return a JSON array of objects with keys: word, definition, example, category. "
        f"Words: {words}"
    )
    try:
        resp = groq_generate_text(system, user)
    except Exception as e:
        resp = None

    # Try to parse output as JSON
    parsed = None
    if resp:
        try:
            parsed = json.loads(resp)
        except Exception:
            # attempt to locate JSON array in response
            start = resp.find('[')
            end = resp.rfind(']')
            if start != -1 and end != -1:
                try:
                    parsed = json.loads(resp[start:end+1])
                except Exception:
                    parsed = None

    # Fallback simple enrichment
    if not parsed:
        parsed = []
        for w in words:
            parsed.append({
                "word": w,
                "definition": f"{w}: (placeholder definition)",
                "example": f"This is an example sentence using the word {w}.",
                "category": "unknown"
            })

    return parsed


def persist_entry(entry):
    # Save to local file
    with OUT_FILE.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry) + "\n")

    # Try to persist to Firestore if available
    try:
        if db:
            # add to known_words via brain.db.add_word
            add_word(entry['word'], entry.get('definition', ''), is_known=True, category=entry.get('category'))
            # store solidified enrichment
            doc = db.collection('solidified_knowledge').document(entry['word'])
            doc.set({
                'enrichment': entry,
                'source': 'batch_enrich',
            })
    except Exception:
        pass


def main():
    print("Loading candidates...")
    candidates = load_candidates()
    print(f"Loaded {len(candidates)} candidates")

    # chunk
    for i in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[i:i+BATCH_SIZE]
        print(f"Enriching batch {i//BATCH_SIZE + 1}: {len(batch)} words")
        enriched = enrich_batch(batch)
        for e in enriched:
            persist_entry(e)
        sleep(DELAY_BETWEEN_BATCHES)

    print(f"Enrichment complete. Results in {OUT_FILE}")


if __name__ == '__main__':
    main()
