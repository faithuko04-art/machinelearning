import logging
from services.researcher import quick_research, research_new_concept
from services.ai_providers import groq_generate_text
from config import APP_CONFIG
import google.generativeai as genai

logger = logging.getLogger(__name__)

def rethink_and_learn(original_prompt: str, incorrect_answer: str) -> str:
    """
    Analyzes a failed response, researches the topic again, and generates a new answer.
    Uses Gemini first, falls back to Groq if Gemini fails.

    Args:
        original_prompt (str): The user's original question.
        incorrect_answer (str): The AI's previous, incorrect answer.

    Returns:
        str: A new, hopefully correct, answer with research and synthesis.
    """
    logger.info(f"Rethinking prompt: '{original_prompt}' after incorrect answer: '{incorrect_answer}'")

    response_parts = []
    response_parts.append("🤔 I understand that my previous answer wasn't correct. Let me research and come up with something better.\n")

    # 1. Perform targeted research
    response_parts.append(f"🔍 **Researching:** '{original_prompt}'")
    try:
        # Try Gemini first for quality research
        new_research = None
        
        if APP_CONFIG.GEMINI_API_KEY:
            try:
                genai.configure(api_key=APP_CONFIG.GEMINI_API_KEY)
                gemini_model = genai.GenerativeModel(APP_CONFIG.GEMINI_MODEL)
                new_research = research_new_concept(original_prompt, gemini_model)
            except Exception as e:
                logger.warning(f"Gemini research failed, falling back to quick research: {e}")
        
        # Fallback to quick research
        if not new_research:
            new_research = quick_research(original_prompt)
        
        if not new_research:
            response_parts.append("\n⚠️ I'm having trouble finding information on this topic. Using what I know...")
            new_research = ""

    except Exception as e:
        logger.error(f"Error during rethink research: {e}", exc_info=True)
        response_parts.append(f"\n⚠️ Research error: {str(e)[:100]}")
        new_research = ""

    # 2. Synthesize new answer using Gemini first, fallback to Groq
    response_parts.append("\n📝 **Synthesizing new answer...**\n")
    
    try:
        system_prompt = (
            "You are an AI assistant who just provided an incorrect answer. "
            "You've done new research and need to provide a corrected, accurate response. "
            "Acknowledge the mistake briefly, then clearly explain the correct information based on the new research."
        )
        
        final_prompt = (
            f"Original Question: {original_prompt}\n\n"
            f"My Previous (Incorrect) Answer: {incorrect_answer}\n\n"
            f"New Research Material:\n{new_research[:1000]}\n\n"
            "Please provide the corrected answer:"
        )

        # Try Gemini first for better quality
        new_answer = None
        if APP_CONFIG.GEMINI_API_KEY:
            try:
                genai.configure(api_key=APP_CONFIG.GEMINI_API_KEY)
                gemini_model = genai.GenerativeModel(APP_CONFIG.GEMINI_MODEL)
                response = gemini_model.generate_content(final_prompt)
                new_answer = response.text
                logger.info("✅ Rethink synthesis with Gemini successful")
            except Exception as e:
                logger.warning(f"Gemini synthesis failed (error: {e}), falling back to Groq")
        
        # Fallback to Groq if Gemini fails
        if not new_answer:
            new_answer = groq_generate_text(system_prompt, final_prompt)
            logger.info("✅ Rethink synthesis with Groq successful (fallback)")
        
        response_parts.append(f"**Corrected Answer:**\n{new_answer}")
        
        # Add learning note
        response_parts.append("\n\n📚 *I'm learning from this correction and will remember it for future questions.*")

    except Exception as e:
        logger.error(f"Error during rethink synthesis: {e}", exc_info=True)
        response_parts.append(f"⚠️ I found new research but had trouble synthesizing it: {str(e)[:100]}\n\nBased on my research: {new_research[:200]}")

    return "\n".join(response_parts)
