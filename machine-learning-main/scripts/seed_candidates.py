"""Seed a candidate word list for batch enrichment.

Behavior:
- Try to generate 500 candidate words via Groq (if configured).
- Fallback to an embedded common-words list if Groq isn't available.
- Writes output to `data/candidates.json` as a JSON array.
"""
import json
import os
from pathlib import Path
try:
    from services.ai_providers import groq_generate_text
    from services.services import groq_client
except Exception:
    groq_generate_text = None
    groq_client = None

OUT_DIR = Path(__file__).parent.parent / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "candidates.json"

DEFAULT_WORDS = [
    # 200 common seeds; will be duplicated if Groq not available to reach 500
    "hello","hi","yes","no","please","thanks","thank","you","I","we",
    "they","he","she","it","what","when","where","why","how","who",
    "name","help","need","want","like","love","hate","good","bad","okay",
    "sorry","apologize","wait","stop","start","open","close","read","write","run",
    "walk","talk","speak","listen","hear","see","look","find","search","ask",
    "answer","question","request","response","helpful","assist","information","data","file","folder",
    "system","user","agent","bot","chat","conversation","message","email","phone","contact",
    "time","date","today","tomorrow","yesterday","morning","evening","night","soon","later",
    "home","work","office","school","university","city","country","place","room","kitchen",
    "food","water","drink","eat","cook","buy","sell","price","cost","cheap",
    "book","read","story","movie","music","song","play","pause","stop","start",
    "weather","temperature","rain","sun","cloud","wind","snow","storm","forecast","climate",
    "money","bank","account","card","pay","transfer","balance","deposit","withdraw","invoice",
    "computer","laptop","phone","tablet","screen","keyboard","mouse","internet","network","wifi",
    "learn","teach","study","course","lesson","practice","exercise","test","quiz","grade",
    "health","doctor","hospital","medicine","disease","pain","cure","symptom","treatment","checkup",
    "sport","game","team","player","score","win","lose","match","league","season",
    "car","vehicle","drive","ride","bus","train","plane","airport","ticket","journey",
    "family","mother","father","sister","brother","child","parent","spouse","friend","neighbor",
    "computer","code","program","script","developer","engineer","design","deploy","build","test",
    "security","password","login","logout","auth","encrypt","access","permission","role","policy",
    "error","bug","fix","debug","trace","log","info","warning","critical","exception",
    "project","task","issue","todo","plan","goal","milestone","deadline","priority","status",
    "art","design","photo","image","paint","draw","color","style","theme","layout",
    "science","biology","chemistry","physics","math","statistics","experiment","research","study","paper",
]


def try_groq_generate_500():
    if not groq_client:
        return None

    system = "You are a helpful assistant that generates a JSON array of single-word English terms suitable for conversational AI training."
    user = (
        "Provide exactly 500 common English words (lemmas, lowercased) useful for building a conversational AI. "
        "Return a JSON array, e.g. [\"hello\", \"world\", ...]. Do not include commentary."
    )

    try:
        raw = groq_generate_text(system, user)
        # Attempt to parse JSON from the response
        cand = None
        try:
            cand = json.loads(raw)
        except Exception:
            # Try to extract bracketed content
            start = raw.find('[')
            end = raw.rfind(']')
            if start != -1 and end != -1:
                cand = json.loads(raw[start:end+1])

        if isinstance(cand, list) and len(cand) >= 50:
            return [w.strip().lower() for w in cand][:500]
    except Exception:
        pass
    return None


def build_fallback_500():
    out = []
    i = 0
    while len(out) < 500:
        out.extend(DEFAULT_WORDS)
        i += 1
        if i > 10:
            break
    return list(dict.fromkeys([w.lower() for w in out]))[:500]


def main():
    print("Seeding candidate list...")
    candidates = try_groq_generate_500()
    if candidates:
        print(f"Generated {len(candidates)} candidates via Groq")
    else:
        candidates = build_fallback_500()
        print(f"Groq not available — using fallback list ({len(candidates)} words)")

    with OUT_FILE.open('w', encoding='utf-8') as f:
        json.dump(candidates, f, indent=2)

    print(f"Wrote {len(candidates)} candidates to {OUT_FILE}")


if __name__ == '__main__':
    main()
