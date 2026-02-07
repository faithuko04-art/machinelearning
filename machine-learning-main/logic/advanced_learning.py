"""Advanced learning module with scheduled background learning and deep learning capabilities."""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List
from services.services import db
from services.ai_providers import groq_generate_text
from services.researcher import quick_research, research_new_concept
from utils.categorizer import categorize_text
from utils.relationship_mapper import find_and_map_relationships
from brain.db import get_unknown_words, add_word, is_known
import google.generativeai as genai
from config import APP_CONFIG

logger = logging.getLogger(__name__)

# Global state
_last_learning_run = None
LEARNING_INTERVAL = 60  # 1 minute in seconds


def should_run_learning() -> bool:
    """Check if enough time has passed since last learning run."""
    global _last_learning_run
    
    if _last_learning_run is None:
        return True
    
    elapsed = time.time() - _last_learning_run
    return elapsed >= LEARNING_INTERVAL


def quick_learn_unknowns() -> Dict:
    """Quick learning of unknown concepts using Groq (fast, every 1 minute)."""
    global _last_learning_run
    
    if not should_run_learning():
        return {"status": "skipped", "reason": "Not enough time has passed"}
    
    logger.info("🚀 Starting quick learning cycle...")
    _last_learning_run = time.time()
    
    results = {
        "status": "started",
        "learned_count": 0,
        "errors": [],
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        unknown_words = get_unknown_words()
        if not unknown_words:
            results["status"] = "no_unknowns"
            return results
        
        for word_doc in unknown_words[:3]:  # Learn top 3 unknowns per cycle
            word = word_doc.id
            logger.info(f"Learning unknown concept: {word}")
            
            try:
                # Quick research via web
                explanation = quick_research(word)
                
                # If research failed, synthesize with Groq
                if not explanation:
                    logger.info(f"No research results for {word}, synthesizing with Groq...")
                    try:
                        system_prompt = f"You are a quick explainer. Provide a brief explanation of '{word}'."
                        prompt = f"Explain '{word}' in 1-2 sentences."
                        explanation = groq_generate_text(system_prompt, prompt)
                        if explanation:
                            logger.info(f"✅ Synthesized explanation for {word} with Groq")
                    except Exception as e:
                        logger.debug(f"Could not synthesize {word}: {e}")
                
                if not explanation:
                    results["errors"].append(f"{word}: No explanation available")
                    continue
                
                # Use Groq for fast categorization
                system_prompt = "Classify this text into: Factual, Conceptual, Procedural, or Adversarial. Respond with just the category."
                category = groq_generate_text(system_prompt, f"Text: {explanation[:500]}")
                
                # Add to knowledge base
                add_word(word, explanation, is_known=True, category=category.strip())
                
                # Try to map relationships (gracefully skip if fails)
                try:
                    find_and_map_relationships(word)
                except Exception as e:
                    logger.debug(f"Could not map relationships for {word}: {e}")
                
                results["learned_count"] += 1
                logger.info(f"✅ Learned: {word}")
                
            except Exception as e:
                err_type = e.__class__.__name__
                error_msg = {
                    "word": word,
                    "type": err_type,
                    "message": str(e)
                }
                results["errors"].append(error_msg)
                logger.error(f"Error learning {word}: {err_type}: {e}", exc_info=True)
        
        results["status"] = "completed"
        return results
        
    except Exception as e:
        results["status"] = "error"
        results["errors"].append(str(e))
        logger.error(f"Error in quick learning: {e}", exc_info=True)
        return results


def deep_learning() -> Dict:
    """Deep learning mode - expands knowledge on both known and unknown concepts.
    Uses Gemini for quality, falls back to Groq if unavailable."""
    
    logger.info("🧠 Starting deep learning cycle...")
    
    results = {
        "status": "started",
        "deepened_known": 0,
        "learned_unknown": 0,
        "errors": [],
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # Get both known and unknown words for deep learning
        unknown_words = get_unknown_words()
        
        # Deep learn unknowns first
        for word_doc in unknown_words:
            word = word_doc.id
            logger.info(f"Deep learning unknown: {word}")
            
            try:
                explanation = None
                
                # Step 1: Try Gemini research first
                if APP_CONFIG.GEMINI_API_KEY:
                    try:
                        genai.configure(api_key=APP_CONFIG.GEMINI_API_KEY)
                        gemini_model = genai.GenerativeModel(APP_CONFIG.GEMINI_MODEL)
                        explanation = research_new_concept(word, gemini_model)
                    except Exception as e:
                        logger.warning(f"Gemini research failed for {word}: {e}, trying quick research")
                
                # Step 2: If Gemini didn't work, try quick search
                if not explanation:
                    explanation = quick_research(word)
                
                # Step 3: If research found nothing, use Groq to synthesize from general knowledge
                if not explanation:
                    logger.info(f"No research results for {word}, synthesizing with Groq...")
                    try:
                        system_prompt = f"You are an expert educator. Provide a clear, concise explanation of '{word}' suitable for learning."
                        prompt = f"Explain '{word}' in 2-3 sentences, including what it is and its main purpose or characteristics."
                        explanation = groq_generate_text(system_prompt, prompt)
                        
                        if explanation:
                            logger.info(f"✅ Synthesized explanation for {word} with Groq")
                    except Exception as e:
                        logger.debug(f"Could not synthesize explanation for {word}: {e}")
                
                if not explanation:
                    results["errors"].append(f"{word}: No explanation could be generated")
                    continue
                
                # Categorize
                if APP_CONFIG.GEMINI_API_KEY:
                    try:
                        gemini_model = genai.GenerativeModel(APP_CONFIG.GEMINI_MODEL)
                        category = categorize_text(explanation, gemini_model)
                    except:
                        category = "Conceptual"
                else:
                    category = "Conceptual"
                
                # Add to knowledge
                add_word(word, explanation, is_known=True, category=category)
                
                # Try to map relationships (gracefully skip if fails)
                try:
                    find_and_map_relationships(word)
                except Exception as e:
                    logger.debug(f"Could not map relationships for {word}: {e}")
                
                results["learned_unknown"] += 1
                logger.info(f"✅ Deep learned: {word}")
                
            except Exception as e:
                err_type = e.__class__.__name__
                error_msg = {
                    "word": word,
                    "type": err_type,
                    "message": str(e)
                }
                results["errors"].append(error_msg)
                logger.error(f"Error deep learning {word}: {err_type}: {e}", exc_info=True)
        
        # Now deepen knowledge on existing known concepts
        try:
            if db:
                known_docs = db.collection('solidified_knowledge').limit(5).stream()
                for doc in known_docs:
                    word = doc.id
                    if word in ['solidified_knowledge', '_default_', 'sentence_patterns']:
                        continue
                    
                    logger.info(f"Deepening knowledge: {word}")
                    
                    try:
                        current_data = doc.to_dict()
                        current_explanation = current_data.get('definition', '')
                        
                        # Use Gemini to expand knowledge
                        if APP_CONFIG.GEMINI_API_KEY:
                            try:
                                genai.configure(api_key=APP_CONFIG.GEMINI_API_KEY)
                                gemini_model = genai.GenerativeModel(APP_CONFIG.GEMINI_MODEL)
                                
                                expansion_prompt = f"""Expand and deepen this explanation of '{word}':
Current: {current_explanation[:300]}

Provide:
1. More detailed explanation
2. Practical applications
3. Related concepts
4. Common misconceptions"""
                                
                                expanded = gemini_model.generate_content(expansion_prompt).text
                                
                                # Update knowledge
                                db.collection('solidified_knowledge').document(word).update({
                                    'expanded_definition': expanded,
                                    'last_deepened': datetime.now().isoformat()
                                })
                                
                                results["deepened_known"] += 1
                                logger.info(f"✅ Deepened: {word}")
                                
                            except Exception as e:
                                logger.debug(f"Could not deepen {word} with Gemini: {e}")
                        
                    except Exception as e:
                        logger.debug(f"Error deepening {word}: {e}")
        
        except Exception as e:
            logger.error(f"Error accessing known concepts: {e}")
        
        results["status"] = "completed"
        return results
        
    except Exception as e:
        results["status"] = "error"
        results["errors"].append(str(e))
        logger.error(f"Error in deep learning: {e}", exc_info=True)
        return results
