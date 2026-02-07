from celery import Celery
import os
from services.services import db
from logic.advanced_learning import quick_learn_unknowns, deep_learning
import logging
import time

logger = logging.getLogger(__name__)

CELERY_BROKER = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
celery_app = Celery("tasks", broker=CELERY_BROKER)


@celery_app.task(name='api.tasks.run_learning_job')
def run_learning_job(job_id: str, mode: str = 'quick'):
    job_ref = db.collection('jobs').document(job_id)
    job_ref.update({'status': 'running', 'started_at': __import__('datetime').datetime.utcnow().isoformat(), 'progress': 0})

    try:
        if mode == 'deep':
            result = deep_learning()
        else:
            result = quick_learn_unknowns()

        # store result
        job_ref.update({'status': 'completed', 'progress': 100, 'result': result, 'finished_at': __import__('datetime').datetime.utcnow().isoformat()})
        return True
    except Exception as e:
        logger.exception(f"Job {job_id} failed: {e}")
        job_ref.update({'status': 'failed', 'errors': [str(e)], 'finished_at': __import__('datetime').datetime.utcnow().isoformat()})
        return False


@celery_app.task(name='api.tasks.run_big_learning_job')
def run_big_learning_job(job_id: str):
    """Run a raw data training loop up to 10 minutes. Each round:
    - Ask LLM (Groq) to generate ~1000 words
    - Tokenize/split and store tokens to Firestore under collection `raw_training/{job_id}`
    - For new tokens: web-research definitions, avoid duplicates, and perform enrichment
    - Update job progress and stop when 10 minutes elapsed
    """
    job_ref = db.collection('jobs').document(job_id)
    job_ref.update({'status': 'running', 'started_at': __import__('datetime').datetime.utcnow().isoformat(), 'progress': 0})

    start = time.monotonic()
    max_seconds = 10 * 60  # 10 minutes
    round_idx = 0
    total_tokens = 0

@celery_app.task(name='api.tasks.finalize_concept')
def finalize_concept(concept_id: str, job_id: str = None):
    """Finalize a concept: read from Neo4j (if available), write canonical doc to Firestore,
    and mark the Neo4j node as finalized.
    """
    job_ref = None
    try:
        if job_id:
            job_ref = db.collection('jobs').document(job_id)
            job_ref.update({'status': 'running', 'progress': 0})
    except Exception:
        job_ref = None

    try:
        # try to read node from Neo4j
        node = None
        try:
            from services.neo4j_helper import fetch_node, update_node_status
            node = fetch_node(concept_id)
        except Exception:
            node = None

        # canonicalize fields
        label = (node.get('label') if node else concept_id) or concept_id
        category = (node.get('category') if node else 'unknown')
        definition = (node.get('definition') if node else '')

        doc = {
            'id': concept_id,
            'label': label,
            'category': category,
            'definition': definition,
            'status': 'final',
            'finalized_at': __import__('datetime').datetime.utcnow().isoformat(),
            'source': 'finalize_task'
        }

        # write to Firestore
        try:
            db.collection('solidified_knowledge').document(concept_id).set(doc)
        except Exception:
            pass

        # compute and store embedding in Chroma (if available)
        try:
            from services.chroma_helper import upsert_knowledge
            # use label + definition as text
            text = f"{label}. {definition or ''}"
            upsert_knowledge(concept_id, text, metadata={'category': category})
        except Exception:
            pass

        # update Neo4j node status
        try:
            if 'update_node_status' in globals() or True:
                from services.neo4j_helper import update_node_status as _uns
                _uns(concept_id, {'status': 'final', 'finalized_at': __import__('datetime').datetime.utcnow().isoformat()})
        except Exception:
            pass

        if job_ref:
            try:
                job_ref.update({'status': 'completed', 'progress': 100})
            except Exception:
                pass
        return True
    except Exception as e:
        if job_ref:
            try:
                job_ref.update({'status': 'failed', 'errors': [str(e)]})
            except Exception:
                pass
        raise


@celery_app.task(name='api.tasks.reconcile_neo4j_firestore')
def reconcile_neo4j_firestore(job_id: str = None, status: str = 'final'):
    """Compare Neo4j nodes with Firestore canonical docs and write a reconciliation report.

    The task will scan Neo4j nodes with `status` and check existence in Firestore.
    Results are written to `jobs/{job_id}/reconcile_report` as a small summary.
    """
    job_ref = None
    try:
        if job_id:
            job_ref = db.collection('jobs').document(job_id)
            job_ref.update({'status': 'running', 'progress': 0})
    except Exception:
        job_ref = None

    try:
        from services.neo4j_helper import fetch_nodes_by_status
        nodes = fetch_nodes_by_status(status=status, limit=5000)
        missing = []
        total = len(nodes)
        checked = 0
        for n in nodes:
            checked += 1
            cid = n.get('id')
            try:
                doc = db.collection('solidified_knowledge').document(cid).get()
                if not doc.exists:
                    missing.append(cid)
            except Exception:
                # assume missing if Firestore not available
                missing.append(cid)

            if job_ref and checked % 100 == 0:
                try:
                    job_ref.update({'progress': int((checked/total)*100), 'checked': checked})
                except Exception:
                    pass

        report = {'total': total, 'missing_count': len(missing), 'missing': missing[:200]}
        if job_ref:
            try:
                job_ref.update({'status': 'completed', 'progress': 100, 'reconcile_report': report})
            except Exception:
                pass

        return report
    except Exception as e:
        if job_ref:
            try:
                job_ref.update({'status': 'failed', 'errors': [str(e)]})
            except Exception:
                pass
        raise

    from services.ai_providers import groq_generate_text
    from services.researcher import quick_research
    from brain.db import is_known, add_word

    # keep track of processed tokens across rounds to avoid duplication
    job_doc = job_ref.get().to_dict()
    processed = set(job_doc.get('processed_tokens', [])) if job_doc else set()

    try:
        while True:
            elapsed = time.monotonic() - start
            if elapsed >= max_seconds:
                logger.info(f"Big job {job_id}: time limit reached ({elapsed:.1f}s). Stopping")
                break

            round_idx += 1
            logger.info(f"Big job {job_id}: starting round {round_idx}")

            # Request LLM to generate ~1000 words in plain text (comma/newline separated)
            system_prompt = "You are a generator. Produce an unordered list of approximately 1000 unique English words or short phrases (1-3 words each)."
            prompt = "Generate approximately 1000 unique words or short phrases, separated by commas."

            try:
                generated = groq_generate_text(system_prompt, prompt)
            except Exception as e:
                logger.exception(f"Big job {job_id}: generation failed: {e}")
                job_ref.update({'errors': [str(e)]})
                break

            if not generated or len(generated.strip()) == 0:
                logger.warning(f"Big job {job_id}: empty generation on round {round_idx}")
                time.sleep(1)
                continue

            # Tokenize: normalize and split
            raw = generated.replace('\n', ',')
            candidates = [c.strip() for c in raw.split(',') if c.strip()]

            # persist raw tokens for audit
            batch = db.batch()
            collection_ref = db.collection('raw_training').document(job_id).collection('rounds')
            for i, cand in enumerate(candidates):
                doc_id = f"r{round_idx}_t{i}"
                batch.set(collection_ref.document(doc_id), {
                    'token': cand,
                    'round': round_idx,
                    'created_at': __import__('datetime').datetime.utcnow().isoformat()
                })
            batch.commit()

            # filter new candidates: not already processed and not known
            new_candidates = []
            for cand in candidates:
                key = cand.lower()
                if key in processed:
                    continue
                if is_known(cand):
                    processed.add(key)
                    continue
                processed.add(key)
                new_candidates.append(cand)

            # Process a bounded number per round to control time
            max_process = 200
            to_process = new_candidates[:max_process]

            # For each new candidate: research definition then enrich via Groq
            for idx, word in enumerate(to_process):
                # Check elapsed time frequently
                if time.monotonic() - start >= max_seconds:
                    logger.info(f"Big job {job_id}: reached time limit during processing")
                    break

                try:
                    # Stage 1/2: quick web research
                    context = quick_research(word)

                    explanation = ""
                    if context:
                        # Try to synthesize a concise explanation using Groq
                        try:
                            sys_prompt = f"You are an expert summarizer. Given the following research snippets, produce a concise definition for '{word}'.\n\n{context}"
                            explanation = groq_generate_text(sys_prompt, f"Provide a 2-3 sentence definition for: {word}")
                        except Exception:
                            explanation = context[:1000]
                    else:
                        # no web context, synthesize directly
                        try:
                            explanation = groq_generate_text("You are an expert educator.", f"Explain '{word}' in 2-3 sentences.")
                        except Exception as e:
                            logger.debug(f"Could not synthesize explanation for {word}: {e}")
                            explanation = ""

                    if explanation:
                        # Stage 2: add to known words
                        try:
                            add_word(word, explanation, is_known=True)
                        except Exception as e:
                            logger.debug(f"Failed to add word {word}: {e}")

                        # Stage 3: multidimensional enrichment via Groq
                        try:
                            enrich_prompt = (
                                f"For the term '{word}', return a JSON object with keys: definition (string), related (array of 5 related concepts), examples (array of 2 examples), category (string). Use concise values."
                            )
                            enrichment = groq_generate_text("You are a knowledge graph builder.", enrich_prompt)
                            # store raw enrichment under solidified_knowledge
                            db.collection('solidified_knowledge').document(word).set({
                                'enrichment': enrichment,
                                'source': 'groq',
                                'created_at': __import__('datetime').datetime.utcnow().isoformat()
                            })
                        except Exception as e:
                            logger.debug(f"Enrichment failed for {word}: {e}")

                    # update progress per processed token
                    total_tokens += 1
                    progress = min(99, int(((time.monotonic() - start) / max_seconds) * 100))
                    job_ref.update({'progress': progress, 'last_round': round_idx, 'total_tokens': total_tokens, 'processed_tokens': list(processed)})

                except Exception as e:
                    logger.exception(f"Error processing token {word}: {e}")
                    job_ref.update({'errors': [str(e)]})

            # brief pause
            time.sleep(0.5)

        # finalize job
        job_ref.update({'status': 'completed', 'progress': 100, 'rounds': round_idx, 'total_tokens': total_tokens, 'finished_at': __import__('datetime').datetime.utcnow().isoformat()})
        return True

    except Exception as e:
        logger.exception(f"Big job {job_id} failed: {e}")
        job_ref.update({'status': 'failed', 'errors': [str(e)], 'finished_at': __import__('datetime').datetime.utcnow().isoformat()})
        return False
