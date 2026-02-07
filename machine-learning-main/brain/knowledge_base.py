
import logging
import json
from typing import List, Dict
from datetime import datetime

from services.services import db, nlp, get_health_status
from services.chroma_helper import upsert_knowledge, query_similar, init_chroma
from services.ai_providers import groq_generate_text

logger = logging.getLogger(__name__)

def generate_response_from_knowledge(prompt_text: str, conversation_context: List = None) -> Dict:
    """
    Generates a response by querying the knowledge base.
    If a strong match is found, it returns the stored knowledge directly.
    Otherwise, it indicates that it needs to learn.
    """
    response_data = {
        "raw_knowledge": None,
        "synthesized_answer": "I am currently unable to process this request as my core services are offline.",
        "prompt": prompt_text
    }

    health = get_health_status()
    if not health['all_services_ok']:
        return response_data

    # Query for the single most similar concept
    similar_concepts = query_similar(prompt_text, n_results=1)

    if similar_concepts:
        top_concept = similar_concepts[0]
        # The 'score' is a distance metric, so lower is better.
        # Let's use a threshold to determine if it's a good match.
        similarity_score = top_concept.get('score', 1.0)
        
        # This threshold may need tuning.
        if similarity_score < 0.6:
            # Found a good match, use the document directly as the answer.
            answer = top_concept.get('document')
            response_data['synthesized_answer'] = answer
            response_data['raw_knowledge'] = [top_concept]
        else:
            # Match is not strong enough
            response_data['synthesized_answer'] = "I don't have enough information to answer that question. I will try to learn about it."
            detect_and_log_unknown_words(prompt_text)
    else:
        # No concepts found
        response_data['synthesized_answer'] = "I don't have enough information to answer that question. I will try to learn about it."
        detect_and_log_unknown_words(prompt_text)

    return response_data

def refine_knowledge_entry(topic: str, knowledge_data: Dict) -> Dict:
    """Refines a knowledge entry using an LLM."""
    logger.info(f"Refining knowledge for: {topic}")

    system_prompt = "You are a knowledge architect. Your task is to refine and improve the provided knowledge entry. Do not change the topic."
    user_prompt = f"Topic: {topic}\n\nKnowledge: {knowledge_data}"
    
    refined_knowledge = groq_generate_text(system_prompt, user_prompt)
    
    return {"refined": True, "refined_knowledge": refined_knowledge, **knowledge_data}

def extract_related_topics(text: str) -> List[str]:
    """Extracts related topics from a given text using an LLM."""
    logger.info(f"Extracting related topics from text.")
    
    system_prompt = "You are an expert in knowledge graph generation. Your task is to extract related topics from the given text. Return the topics as a JSON object with a single key 'topics' which is a list of strings."
    user_prompt = f"Text: {text}"
    
    response = groq_generate_text(system_prompt, user_prompt)
    
    try:
        data = json.loads(response)
        return data.get("topics", [])
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from LLM response: {response}")
        return []

def detect_and_log_unknown_words(prompt: str):
    """
    Detects candidate unknown concepts from the prompt using spaCy noun-chunk
    extraction and token lemmatization, filters out short/stopword tokens, deduplicates
    overlapping phrases, logs the cleaned candidates to Firestore (`needs_review`) and 
    adds them to the `unknown_words` collection for the learning pipeline.
    """
    try:
        candidates = set()
        stopset = {"what", "the", "is", "a", "an", "i", "you", "it", "this", "that", "does", "do", "how", "why", "be", "have", "make", "take", "get", "go", "know", "think", "see", "come", "come", "use", "find", "give", "tell", "work", "call", "ask", "need", "feel", "become", "leave", "put", "mean", "keep", "let", "begin", "seem", "help", "talk", "turn", "start", "show", "hear", "act", "show", "move", "like", "live", "believe", "hold", "bring", "happen", "write", "provide", "sit", "stand", "lose", "pay", "meet", "include", "continue", "set", "learn", "change", "lead", "understand", "watch", "follow", "stop", "create", "speak", "read", "allow", "add", "spend", "grow", "open", "walk", "win", "offer", "remember", "love", "consider", "appear", "buy", "wait", "serve", "die", "send", "expect", "build", "stay", "fall", "cut", "reach", "kill", "remain", "suggest", "raise", "pass", "sell", "require", "report", "decide", "pull", "explain", "develop", "carry", "break", "receive", "agree", "support", "hit", "produce", "eat", "cover", "catch", "draw", "choose", "strike", "manage", "shake", "drink", "choose", "share", "spread", "prepare", "speak", "try", "release", "search", "charge", "race", "climb", "rush", "mix", "mark", "fight", "fit", "establish", "cook", "jump", "laugh", "apply", "spend", "score", "operate", "divide", "sign", "hang", "rest", "serve", "sing", "arrive", "return", "visit", "teach", "earn", "travel", "fly", "damage", "solve", "wrestle", "swim", "teach", "hunt", "achieve", "establish", "throw", "destroy", "dance", "suffer", "start", "spend", "trade", "slip", "protect", "represent", "join", "drive", "repair", "master", "suffer", "behave", "command", "ring", "pray", "notice", "reflect", "blame", "regret", "admit", "suffer", "extend", "waste", "supply", "retire", "employ", "escape", "grant", "resolve", "prove", "install", "engage", "generate", "inherit", "adopt", "succeed", "admit", "submit", "embrace", "suffer"}

        if nlp:
            doc = nlp(prompt)

            # Extract meaningful noun chunks (multi-word candidate phrases)
            for chunk in doc.noun_chunks:
                # Build lemmatized phrase from non-stop alphabetic tokens
                lemmas = [tok.lemma_.lower() for tok in chunk if not tok.is_stop and tok.is_alpha]
                if not lemmas:
                    continue
                phrase = " ".join(lemmas).strip()
                if len(phrase) >= 3 and phrase not in stopset:
                    candidates.add(phrase)

            # Also extract single-token nouns/proper nouns
            for tok in doc:
                if tok.pos_ in ("NOUN", "PROPN") and not tok.is_stop and tok.is_alpha:
                    lemma = tok.lemma_.lower()
                    if len(lemma) >= 3 and lemma not in stopset:
                        candidates.add(lemma)
        else:
            # Fallback: very simple heuristic split
            for part in prompt.split():
                word = ''.join(ch for ch in part.lower() if ch.isalpha())
                if len(word) >= 4 and word not in stopset:
                    candidates.add(word)

        # Deduplication: remove single tokens if they appear in multi-word phrases
        dedup_candidates = set(candidates)
        for phrase in list(dedup_candidates):
            if " " in phrase:  # Multi-word phrase
                for token in phrase.split():
                    dedup_candidates.discard(token)

        # Save review entry with cleaned candidates and original prompt
        if db:
            try:
                review_ref = db.collection('needs_review').document()
                review_ref.set({
                    'prompt': prompt,
                    'candidates': sorted(list(dedup_candidates)),
                    'reason': 'Extracted candidate unknown concepts (deduplicated)',
                    'timestamp': datetime.utcnow()
                })
                logger.info(f"Logged prompt for review with deduplicated candidates: {dedup_candidates}")

                # Add each candidate to unknown_words collection for learning pipeline
                from brain.db import add_word
                for cand in dedup_candidates:
                    try:
                        # add_word with is_known=False will create an entry in unknown_words
                        add_word(cand, explanation="", is_known=False)
                    except Exception as e:
                        logger.debug(f"Failed to add unknown candidate {cand}: {e}")

            except Exception as e:
                logger.error(f"Error logging prompt for review: {e}", exc_info=True)
        else:
            logger.warning("No Firestore DB available to log unknowns.")

    except Exception as e:
        logger.error(f"Error in detect_and_log_unknown_words: {e}", exc_info=True)
