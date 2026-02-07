import logging
from services.services import db

try:
    from nltk.corpus import wordnet
except Exception:
    # Attempt to download WordNet if missing when first used
    import nltk
    try:
        nltk.download('wordnet')
        from nltk.corpus import wordnet
    except Exception as e:
        # If download fails, set wordnet to None and handle later
        wordnet = None
        logging.getLogger(__name__).warning(f"WordNet unavailable and download failed: {e}")

logger = logging.getLogger(__name__)

def find_and_map_relationships(word):
    """
    Finds and maps relationships for a given word using WordNet.
    Gracefully skips if WordNet is unavailable.
    """
    logger.info(f"Finding relationships for: {word}")
    
    # Ensure WordNet is available
    if not wordnet:
        logger.debug("WordNet is not available. Skipping relationship mapping.")
        return
    
    try:
        # Get the synsets for the word
        synsets = wordnet.synsets(word)
        
        if not synsets:
            logger.debug(f"No WordNet synsets found for '{word}'.")
            return

        # Use the first synset as the primary one
        main_synset = synsets[0]

        # Get hypernyms (more general concepts)
        hypernyms = main_synset.hypernyms()
        hypernym_names = [h.lemmas()[0].name() for h in hypernyms]

        # Get hyponyms (more specific concepts)
        hyponyms = main_synset.hyponyms()
        hyponym_names = [h.lemmas()[0].name() for h in hyponyms]

        # Get meronyms (parts of)
        part_meronyms = main_synset.part_meronyms()
        part_meronym_names = [m.lemmas()[0].name() for m in part_meronyms]

        # Get holonyms (wholes that this is a part of)
        member_holonyms = main_synset.member_holonyms()
        member_holonym_names = [h.lemmas()[0].name() for h in member_holonyms]

        # Update Firestore with the new relationships
        doc_ref = db.collection('solidified_knowledge').document(word)
        doc_ref.update({
            'related_to': list(set(hypernym_names + member_holonym_names)),
            'subtopics': list(set(hyponym_names + part_meronym_names))
        })

        logger.info(f"Mapped relationships for '{word}':")
        logger.debug(f"  - Hypernyms (related_to): {hypernym_names}")
        logger.debug(f"  - Hyponyms (subtopics): {hyponym_names}")
        logger.debug(f"  - Meronyms (subtopics): {part_meronym_names}")
        logger.debug(f"  - Holonyms (related_to): {member_holonym_names}")
    
    except LookupError as e:
        logger.debug(f"WordNet resource missing for relationship mapping: {e}")
        # Silently skip - this is expected if wordnet corpus not downloaded
    except Exception as e:
        logger.debug(f"Error mapping relationships for '{word}': {e}")
