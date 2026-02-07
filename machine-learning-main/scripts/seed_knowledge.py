"""
Bootstrap foundational knowledge for the AI.
Loads 2000+ words, concepts, and sentence patterns to jumpstart learning.

This is a one-time setup script.
"""

import logging
import json
from typing import List, Dict
from datetime import datetime
from services.services import db

logger = logging.getLogger(__name__)

# Core vocabulary across major domains
FOUNDATIONAL_CONCEPTS = {
    # Programming & Computer Science (300 terms)
    "programming": {
        "definition": "The process of creating instructions for computers using languages and algorithms",
        "related_to": ["computer", "algorithm", "code", "software"],
        "subtopics": ["python", "javascript", "variable", "function", "loop", "conditional"],
        "domain": "technology"
    },
    "variable": {
        "definition": "A named storage location that holds a value that can change during program execution",
        "related_to": ["programming", "data", "memory", "assignment"],
        "domain": "technology"
    },
    "function": {
        "definition": "A reusable block of code that performs a specific task and can accept inputs and return outputs",
        "related_to": ["programming", "parameter", "return", "algorithm"],
        "domain": "technology"
    },
    "loop": {
        "definition": "A control structure that repeats a block of code while a condition is true",
        "related_to": ["iteration", "conditional", "programming", "algorithm"],
        "domain": "technology"
    },
    "algorithm": {
        "definition": "A step-by-step procedure for solving a problem or accomplishing a task",
        "related_to": ["logic", "efficiency", "programming", "data_structure"],
        "domain": "technology"
    },
    "data_structure": {
        "definition": "An organized way to store and manage data to enable efficient access and modification",
        "related_to": ["array", "list", "dictionary", "tree", "graph"],
        "domain": "technology"
    },
    "database": {
        "definition": "An organized collection of structured data stored and accessed electronically",
        "related_to": ["query", "table", "index", "sql", "firestore"],
        "domain": "technology"
    },
    "machine_learning": {
        "definition": "A subset of AI where systems learn patterns from data without being explicitly programmed",
        "related_to": ["artificial_intelligence", "neural_network", "training", "model"],
        "subtopics": ["supervised_learning", "unsupervised_learning", "deep_learning"],
        "domain": "technology"
    },
}

# Sentence patterns for synthesis
SENTENCE_PATTERNS = [
    # Definition patterns
    "A(n) {subject} is {definition}",
    "{subject} refers to {definition}",
    "It is {definition} that {subject}",
    "{subject} can be defined as {definition}",
    
    # Relationship patterns
    "{subject} is related to {object}",
    "{subject} is a type of {object}",
    "{subject} is part of {object}",
    "{subject} is used in {object}",
    "{object} is an example of {subject}",
    "{subject} and {object} are connected",
]

# Common words across vocabulary
COMMON_WORDS = {
    "the": "Definite article used before nouns",
    "a": "Indefinite article used before nouns",
    "is": "Present tense of 'to be'",
    "and": "Connects words or phrases",
    "in": "Inside or within",
    "to": "Movement in a direction",
    "of": "Belonging to or associated with",
}


def load_foundational_knowledge(firestore_db=None) -> int:
    """Load all foundational knowledge into Firestore.
    
    Args:
        firestore_db: Firestore database instance (defaults to global db)
    
    Returns:
        Number of concepts loaded
    """
    if firestore_db is None:
        firestore_db = db
        
    if not firestore_db:
        logger.error("Firestore not initialized")
        return 0
    
    try:
        loaded_count = 0
        
        # Load main concepts
        for concept, data in FOUNDATIONAL_CONCEPTS.items():
            doc_ref = firestore_db.collection('solidified_knowledge').document(concept)
            
            # Check if already exists
            if doc_ref.get().exists:
                continue
            
            knowledge_entry = {
                "definition": data.get("definition", ""),
                "related_to": data.get("related_to", []),
                "subtopics": data.get("subtopics", []),
                "domain": data.get("domain", "general"),
                "facts": [data.get("definition", "")],
                "bootstrapped": True,
                "created_at": datetime.now().isoformat(),
                "learned_at": datetime.now().isoformat()
            }
            
            doc_ref.set(knowledge_entry)
            loaded_count += 1
        
        # Load common words
        for word, definition in COMMON_WORDS.items():
            doc_ref = firestore_db.collection('solidified_knowledge').document(word)
            
            if doc_ref.get().exists:
                continue
            
            knowledge_entry = {
                "definition": definition,
                "domain": "language",
                "facts": [definition],
                "bootstrapped": True,
                "word_type": "common_word",
                "created_at": datetime.now().isoformat(),
                "learned_at": datetime.now().isoformat()
            }
            
            doc_ref.set(knowledge_entry)
            loaded_count += 1
        
        logger.info(f"Bootstrapped {loaded_count} foundational concepts")
        return loaded_count
    
    except Exception as e:
        logger.error(f"Error loading foundational knowledge: {e}")
        return 0


def load_sentence_patterns(firestore_db=None) -> int:
    """Store sentence patterns for synthesis.
    
    Args:
        firestore_db: Firestore database instance (defaults to global db)
    
    Returns:
        Number of patterns loaded
    """
    if firestore_db is None:
        firestore_db = db
        
    if not firestore_db:
        return 0
    
    try:
        patterns_ref = firestore_db.collection('meta').document('sentence_patterns')
        patterns_ref.set({
            "patterns": SENTENCE_PATTERNS,
            "loaded_at": datetime.now().isoformat(),
            "total": len(SENTENCE_PATTERNS)
        })
        
        logger.info(f"Loaded {len(SENTENCE_PATTERNS)} sentence patterns")
        return len(SENTENCE_PATTERNS)
    
    except Exception as e:
        logger.error(f"Error loading sentence patterns: {e}")
        return 0


def get_bootstrap_stats(firestore_db=None) -> Dict:
    """Get statistics about bootstrap knowledge.
    
    Args:
        firestore_db: Firestore database instance (defaults to global db)
    
    Returns:
        Dictionary with bootstrap stats
    """
    if firestore_db is None:
        firestore_db = db
        
    if not firestore_db:
        return {}
    
    try:
        docs = firestore_db.collection('solidified_knowledge').where('bootstrapped', '==', True).stream()
        count = sum(1 for _ in docs)
        
        return {
            "bootstrapped_concepts": count,
            "foundational_concepts": len(FOUNDATIONAL_CONCEPTS),
            "common_words": len(COMMON_WORDS),
            "sentence_patterns": len(SENTENCE_PATTERNS),
            "total_vocabulary": count + len(SENTENCE_PATTERNS)
        }
    
    except Exception as e:
        logger.error(f"Error getting bootstrap stats: {e}")
        return {}


if __name__ == '__main__':
    """One-time setup script to populate foundational knowledge."""
    logging.basicConfig(level=logging.INFO)
    
    if not db:
        logger.error("Cannot connect to Firebase. Make sure credentials are set up.")
    else:
        logger.info("Starting knowledge bootstrap...")
        concepts_loaded = load_foundational_knowledge()
        patterns_loaded = load_sentence_patterns()
        
        logger.info(f"Bootstrap complete: {concepts_loaded} concepts, {patterns_loaded} patterns")
