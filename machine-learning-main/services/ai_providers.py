import logging
from services.services import groq_client
from config import APP_CONFIG

logger = logging.getLogger(__name__)

def _try_gemini(prompt):
    """Attempts to generate content using the Gemini API's chat functionality."""
    import google.generativeai as genai
    
    if not APP_CONFIG.GEMINI_API_KEY:
        logger.warning("Gemini provider not configured. Skipping.")
        return None
    try:
        model = genai.GenerativeModel(APP_CONFIG.GEMINI_MODEL)
        resp = model.generate_content(prompt)
        return resp.text
    except Exception as e:
        logger.error(f"Gemini provider failed: {e}", exc_info=True)
        return None

def _try_groq(prompt):
    """DEPRECATED: Use groq_generate_text for more control."""
    logger.warning("The _try_groq function is deprecated. Use groq_generate_text instead.")
    if not groq_client:
        logger.warning("Groq provider not configured. Skipping.")
        return None


    def _try_ignis(prompt):
        """Attempt to call an Ignis endpoint (a local or remote model API).

        Expects APP_CONFIG.IGNIS_API_URL to be set to an HTTP endpoint that accepts
        JSON {"prompt": "..."} and returns JSON {"response": "..."}.
        """
        url = getattr(APP_CONFIG, 'IGNIS_API_URL', None)
        if not url:
            return None
        try:
            import requests
            resp = requests.post(url, json={'prompt': prompt}, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('response') or data.get('text') or resp.text
            return None
        except Exception as e:
            logger.error(f"Ignis provider failed: {e}", exc_info=True)
            return None
    try:
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
        resp = groq_client.chat.completions.create(
            messages=messages, 
            model=APP_CONFIG.GROQ_MODEL
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq provider failed: {e}", exc_info=True)
        return None

def groq_generate_text(system_prompt: str, user_prompt: str):
    """Generates a response from Groq using a system and user prompt.

    Args:
        system_prompt: The system-level instruction for the model.
        user_prompt: The user's query or prompt.

    Returns:
        The generated text as a string, or a default message if it fails.
    """
    if not groq_client:
        logger.warning("Groq provider not configured. Cannot generate text.")
        return "Groq provider is not available."
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        resp = groq_client.chat.completions.create(
            messages=messages, 
            model=APP_CONFIG.GROQ_MODEL
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq provider failed: {e}", exc_info=True)
        return "I am having trouble accessing my knowledge base at the moment."

def generate_text(prompt, prefer=None):
    """Generate text from available providers, with fallback.

    Args:
        prompt: The input prompt for the AI.
        prefer: A tuple or list specifying the preferred order of providers (e.g., ('gemini', 'groq')).

    Returns:
        The generated text as a string, or raises a RuntimeError if all providers fail.
    """
    if prefer is None:
        prefer = ('ignis', 'gemini', 'groq')

    logger.info(f"Generating text with provider preference: {prefer}")

    for provider in prefer:
        if provider == 'gemini':
            logger.info("Attempting to use Gemini...")
            output = _try_gemini(prompt)
            if output:
                logger.info("Success with Gemini.")
                return {'response': output, 'provider': 'Gemini'}
            logger.warning("Gemini failed. Falling back to next provider.")

        elif provider == 'groq':
            logger.info("Attempting to use Groq...")
            output = _try_groq(prompt)
            if output:
                logger.info("Success with Groq.")
                return {'response': output, 'provider': 'Groq'}
            logger.warning("Groq failed. Falling back to next provider.")
        elif provider == 'ignis':
            logger.info("Attempting to use Ignis...")
            output = _try_ignis(prompt)
            if output:
                logger.info("Success with Ignis.")
                return {'response': output, 'provider': 'Ignis'}
            logger.warning("Ignis failed. Falling back to next provider.")

    # If the loop completes without returning, all providers have failed.
    logger.critical("All LLM providers failed to generate a response.")
    raise RuntimeError("All LLM providers are unavailable or failed.")
