"""
Sentence synthesis and composition using learned patterns and vocabulary.
Generates fluent, contextual responses using learned concepts and relationships.
"""

import logging
import random
from typing import List, Dict, Tuple
from datetime import datetime
from services.services import db

logger = logging.getLogger(__name__)


def get_related_concepts(concept: str, firestore_db=None) -> List[Tuple[str, str]]:
    """Get related concepts from knowledge base.
    
    Args:
        concept: The main concept
        firestore_db: Firestore database instance (defaults to global db)
    
    Returns:
        List of (concept, relationship_type) tuples
    """
    if firestore_db is None:
        firestore_db = db
        
    if not firestore_db:
        return []
    
    try:
        doc = firestore_db.collection('solidified_knowledge').document(concept).get()
        if not doc.exists:
            return []
        
        data = doc.to_dict()
        related_to = data.get('related_to', [])
        subtopics = data.get('subtopics', [])
        
        # Create tuples with relationship types
        relations = [(r, 'related') for r in related_to] + [(s, 'subtopic') for s in subtopics]
        return relations
    
    except Exception as e:
        logger.debug(f"Error getting related concepts: {e}")
        return []


def get_definition(concept: str, firestore_db=None) -> str:
    """Get the definition of a concept.
    
    Args:
        concept: The concept to define
        firestore_db: Firestore database instance (defaults to global db)
    
    Returns:
        Definition string or empty string
    """
    if firestore_db is None:
        firestore_db = db
        
    if not firestore_db:
        return ""
    
    try:
        doc = firestore_db.collection('solidified_knowledge').document(concept).get()
        if doc.exists:
            return doc.to_dict().get('definition', '')
        return ""
    
    except Exception as e:
        logger.debug(f"Error getting definition: {e}")
        return ""


def synthesize_definition_sentence(concept: str, firestore_db=None) -> str:
    """Generate a well-formed definition sentence.
    
    Args:
        concept: The concept to define
        firestore_db: Firestore database instance (defaults to global db)
    
    Returns:
        A grammatically correct definition sentence
    """
    definition = get_definition(concept, firestore_db)
    if not definition:
        return f"{concept} is a concept I have learned about."
    
    # Remove trailing period if present
    definition = definition.rstrip('.')
    
    # Use pattern: "{subject} is {definition}"
    return f"{concept.capitalize()} is {definition}."


def synthesize_relationship_sentence(concept1: str, concept2: str, relationship: str = None) -> str:
    """Generate a sentence describing relationship between concepts.
    
    Args:
        concept1: First concept
        concept2: Second concept
        relationship: Type of relationship (optional)
    
    Returns:
        A sentence describing the relationship
    """
    patterns = [
        f"{concept1} is related to {concept2}.",
        f"{concept1} and {concept2} are connected.",
        f"One of the connections between {concept1} and {concept2} is important.",
        f"In many contexts, {concept1} and {concept2} work together.",
        f"{concept1} helps explain {concept2}.",
        f"{concept2} is an important aspect of {concept1}.",
    ]
    
    if relationship:
        if relationship == "subtopic":
            patterns = [
                f"{concept2} is a subtopic of {concept1}.",
                f"{concept2} is part of the field of {concept1}.",
                f"When studying {concept1}, you encounter {concept2}.",
            ]
        elif relationship == "related":
            patterns = [
                f"{concept1} and {concept2} are closely related.",
                f"Understanding {concept1} requires knowledge of {concept2}.",
                f"Both {concept1} and {concept2} are important in this field.",
            ]
    
    return random.choice(patterns)


def synthesize_paragraph(concept: str, firestore_db=None) -> str:
    """Generate a multi-sentence paragraph about a concept.
    
    Args:
        concept: The main concept
        firestore_db: Firestore database instance (defaults to global db)
    
    Returns:
        A paragraph explaining the concept
    """
    if firestore_db is None:
        firestore_db = db
        
    sentences = []
    
    # First sentence: definition
    sentences.append(synthesize_definition_sentence(concept, firestore_db))
    
    # Add related concepts
    related = get_related_concepts(concept, firestore_db)
    if related:
        # Pick 2-3 random related concepts
        sample_relations = random.sample(related, min(3, len(related)))
        
        for rel_concept, rel_type in sample_relations:
            sentence = synthesize_relationship_sentence(concept, rel_concept, rel_type)
            sentences.append(sentence)
    else:
        # Fallback sentence
        sentences.append(f"There are many aspects to {concept} worth exploring.")
    
    # Add reflection
    sentences.append(f"Understanding {concept} is important for comprehensive learning.")
    
    return " ".join(sentences)


def synthesize_response(question: str, answer_text: str, learned_concepts: List[str] = None, firestore_db=None) -> str:
    """Synthesize a more sophisticated response incorporating learned knowledge.
    
    Args:
        question: User's question
        answer_text: Base answer text
        learned_concepts: List of concepts mentioned in answer
        firestore_db: Firestore database instance (defaults to global db)
    
    Returns:
        Enhanced response with synthesis
    """
    if firestore_db is None:
        firestore_db = db
        
    response_parts = [answer_text]
    
    if learned_concepts and firestore_db:
        # Add context sentences about learned concepts
        for i, concept in enumerate(learned_concepts[:2]):  # Max 2 concepts
            relationship_concepts = get_related_concepts(concept, firestore_db)
            if relationship_concepts:
                rel_concept, rel_type = random.choice(relationship_concepts)
                relationship_sentence = synthesize_relationship_sentence(
                    concept, rel_concept, rel_type
                )
                response_parts.append(relationship_sentence)
        
        # Add synthesis sentence
        if len(learned_concepts) > 1:
            response_parts.append(
                f"Together, these concepts form a rich understanding of the topic."
            )
    
    return " ".join(response_parts)


def get_sentence_patterns(firestore_db=None) -> List[str]:
    """Retrieve stored sentence patterns.
    
    Args:
        firestore_db: Firestore database instance (defaults to global db)
    
    Returns:
        List of sentence patterns
    """
    if firestore_db is None:
        firestore_db = db
        
    if not firestore_db:
        return []
    
    try:
        doc = firestore_db.collection('meta').document('sentence_patterns').get()
        if doc.exists:
            return doc.to_dict().get('patterns', [])
        return []
    
    except Exception as e:
        logger.debug(f"Error getting sentence patterns: {e}")
        return []


def extract_key_concepts(text: str, firestore_db=None) -> List[str]:
    """Extract learned concepts from response text.
    
    Args:
        text: The response text
        firestore_db: Firestore database instance (defaults to global db)
    
    Returns:
        List of recognized concepts
    """
    if firestore_db is None:
        firestore_db = db
        
    if not firestore_db:
        return []
    
    concepts = []
    
    # Get all learned concepts
    try:
        docs = firestore_db.collection('solidified_knowledge').stream()
        learned_terms = {doc.id for doc in docs}
        
        # Find which learned terms appear in text (case-insensitive)
        text_lower = text.lower()
        for term in learned_terms:
            if term.lower() in text_lower:
                concepts.append(term)
    
    except Exception as e:
        logger.debug(f"Error extracting key concepts: {e}")
    
    return concepts[:5]  # Return top 5


def assess_response_coherence(response: str, concepts: List[str]) -> float:
    """Assess coherence of a response based on concept relationships.
    
    Args:
        response: The response text
        concepts: List of concepts in the response
    
    Returns:
        Coherence score 0-1
    """
    if not concepts or len(concepts) < 2:
        return 0.5  # Baseline for single concept
    
    # Count how many concept pairs appear in the response
    response_lower = response.lower()
    pair_count = 0
    
    for i, c1 in enumerate(concepts):
        for c2 in concepts[i+1:]:
            if c1.lower() in response_lower and c2.lower() in response_lower:
                pair_count += 1
    
    # Coherence = how many concept pairs are mentioned together
    max_pairs = len(concepts) * (len(concepts) - 1) / 2
    if max_pairs == 0:
        return 0.5
    
    coherence = min(1.0, pair_count / max_pairs)
    return coherence


def log_synthesis_learning(concept: str, synthesis_used: bool, firestore_db=None) -> None:
    """Log synthesis activities for learning improvement.
    
    Args:
        concept: The concept synthesized
        synthesis_used: Whether synthesis was applied
        firestore_db: Firestore database instance (defaults to global db)
    """
    if firestore_db is None:
        firestore_db = db
        
    if not firestore_db:
        return
    
    try:
        log_ref = firestore_db.collection('synthesis_logs').document(concept)
        log_ref.set({
            "concept": concept,
            "synthesis_used": synthesis_used,
            "timestamp": datetime.now().isoformat(),
            "date": datetime.now().date().isoformat()
        }, merge=True)
    except Exception as e:
        logger.debug(f"Error logging synthesis: {e}")
