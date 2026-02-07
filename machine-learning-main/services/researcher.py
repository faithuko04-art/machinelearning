# services/researcher.py
import logging
import os
from typing import Optional

# Try DuckDuckGo first, but we have fallbacks
try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False

# Get a logger for this module
logger = logging.getLogger(__name__)


def _search_ddgs(query: str, max_results: int = 5) -> str:
    """DuckDuckGo search (primary method)."""
    if not HAS_DDGS:
        return ""
    
    logger.debug(f"Attempting DuckDuckGo search for: '{query}'")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        
        if results:
            context = " ".join([r.get('body', '') for r in results if r.get('body')])
            logger.info(f"✅ DuckDuckGo found {len(results)} results")
            return context
        else:
            logger.debug("DuckDuckGo: No results found")
            return ""
    except Exception as e:
        logger.debug(f"DuckDuckGo search failed: {e}")
        return ""


def _search_google_custom(query: str, max_results: int = 5) -> str:
    """Google Custom Search Engine (CSE) - requires API key and CX."""
    import requests
    
    api_key = os.environ.get('GOOGLE_API_KEY')
    cx = os.environ.get('GOOGLE_CSE_ID')
    
    if not api_key or not cx:
        return ""
    
    logger.debug(f"Attempting Google CSE search for: '{query}'")
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'q': query,
            'key': api_key,
            'cx': cx,
            'num': min(max_results, 10)
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        results = response.json().get('items', [])
        if results:
            context = " ".join([
                r.get('snippet', '') or r.get('title', '')
                for r in results
            ])
            logger.info(f"✅ Google CSE found {len(results)} results")
            return context
        else:
            logger.debug("Google CSE: No results found")
            return ""
    except Exception as e:
        logger.debug(f"Google CSE search failed: {e}")
        return ""


def _search_groq_tools(query: str, max_results: int = 5) -> str:
    """Use Groq with LLM-based search capability."""
    from services.ai_providers import groq_generate_text
    
    logger.debug(f"Attempting Groq LLM search for: '{query}'")
    try:
        # Use Groq's LLM to search
        system_prompt = "You are a research assistant. Provide factual information based on your knowledge. Be concise."
        prompt = f"Provide information about: {query}\n\nGive only factual information, no introduction."
        
        response = groq_generate_text(system_prompt, prompt)
        if response and len(response.strip()) > 20:  # Ensure we got real content
            logger.info(f"✅ Groq search succeeded")
            return response
        else:
            logger.debug("Groq search returned empty")
            return ""
    except Exception as e:
        logger.debug(f"Groq search failed: {e}")
        return ""


def quick_research(concept: str) -> str:
    """Performs web research for a concept using multiple fallback methods.
    
    Methods tried in order:
    1. DuckDuckGo (if available)
    2. Google Custom Search Engine (if configured)
    3. Groq with LLM-based search
    
    Args:
        concept: The concept to research.
    
    Returns:
        A string containing the concatenated search results, or an empty string if all methods fail.
    """
    logger.info(f"RESEARCHER: Starting quick research for: '{concept}'")
    
    query = f"what is {concept}"
    
    # Try each search method
    search_methods = [
        ("DuckDuckGo", _search_ddgs),
        ("Google CSE", _search_google_custom),
        ("Groq", _search_groq_tools),
    ]
    
    for method_name, method_func in search_methods:
        try:
            result = method_func(query, max_results=5)
            if result and len(result.strip()) > 50:  # Need substantial content
                logger.info(f"RESEARCHER: Successfully retrieved results via {method_name}")
                return result
        except Exception as e:
            logger.debug(f"Search method {method_name} failed: {e}")
            continue
    
    logger.warning(f"RESEARCHER: All search methods failed for '{concept}'. Using fallback synthesis.")
    return ""  # Will trigger Groq synthesis in learning module


def research_new_concept(word: str, llm_client) -> str:
    """Researches a new concept using web search and an LLM for deep analysis.

    Args:
        word: The word or concept to research.
        llm_client: An instance of a generative AI model client (e.g., Gemini).

    Returns:
        A string containing the synthesized explanation of the concept, or an empty string if research fails.
    """
    logger.info(f"RESEARCHER: Starting deep research for new concept: '{word}'")
    context = quick_research(word)

    if not context:
        logger.info(f"RESEARCHER: No web search results for '{word}', will use LLM synthesis only")
        # Return empty string so calling code can use synthesis fallback
        return ""

    # Use the LLM to generate a final, clean explanation
    if llm_client:
        logger.info("RESEARCHER: Synthesizing with LLM.")
        prompt = f"Based on the following information, provide a concise and clear explanation of the term '{word}'. Do not start with introductory phrases like 'Based on the information provided...'. Just give the explanation directly. Information: \n\n{context}"
        
        try:
            response = llm_client.generate_content(prompt)
            explanation = response.text
            logger.info(f"RESEARCHER: Successfully synthesized explanation for '{word}'.")
            return explanation
        except Exception as e:
            logger.warning(f"RESEARCHER: LLM synthesis failed for '{word}': {e}")
            return ""
    else:
        logger.warning("RESEARCHER: LLM client is not available. Cannot synthesize explanation.")
        # Fallback to returning raw context if no LLM is present
        return context
