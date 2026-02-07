from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uuid
import asyncio
from services.services import db
import os
from pathlib import Path
from api.tasks import celery_app
try:
    from services.neo4j_helper import fetch_graph as neo4j_fetch
except Exception:
    neo4j_fetch = None
import json


app = FastAPI(title="Learning Pipeline API")

# Serve static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """Serve the integrated frontend."""
    return FileResponse(str(static_dir / "index.html"))


# (Batch processing is now handled by Celery tasks.)


class StartJobRequest(BaseModel):
    mode: str = "quick"  # quick or deep


@app.post("/jobs/start")
async def start_job(req: StartJobRequest):
    job_id = str(uuid.uuid4())
    # create job doc
    db.collection('jobs').document(job_id).set({
        'status': 'queued',
        'mode': req.mode,
        'created_at': __import__('datetime').datetime.utcnow().isoformat(),
        'progress': 0,
        'errors': []
    })

    # enqueue celery task
    celery_app.send_task('api.tasks.run_learning_job', args=[job_id, req.mode])

    return {"job_id": job_id}


@app.post("/jobs/start_big")
async def start_big_job():
    """Start a long-running raw-data "big learning" job that runs up to 10 minutes."""
    job_id = str(uuid.uuid4())
    db.collection('jobs').document(job_id).set({
        'status': 'queued',
        'mode': 'big',
        'created_at': __import__('datetime').datetime.utcnow().isoformat(),
        'progress': 0,
        'errors': [],
        'meta': {'target_words_per_round': 1000}
    })

    celery_app.send_task('api.tasks.run_big_learning_job', args=[job_id])
    return {"job_id": job_id}



@app.post('/batch/run')
async def run_batch():
    """Start the batch_enrich.py script in background (non-blocking).

    Returns the pid if started. This is a lightweight way to trigger the batch
    processing without requiring Celery in this environment.
    """
    # Create a job document and enqueue a Celery task to process batches.
    job_id = str(uuid.uuid4())
    try:
        db.collection('jobs').document(job_id).set({
            'status': 'queued',
            'mode': 'batch_enrich',
            'created_at': __import__('datetime').datetime.utcnow().isoformat(),
            'progress': 0,
            'errors': []
        })
    except Exception:
        # Firestore may be unavailable; still enqueue the task and return job_id
        pass

    # enqueue Celery task
    celery_app.send_task('api.tasks.run_batch_enrich', args=[job_id])
    return {'status': 'queued', 'job_id': job_id}


@app.get('/batch/status')
async def batch_status():
    """Return batch job status. If `job_id` query param provided, return that job's status.
    Otherwise fall back to file counts when Firestore isn't available.
    """
    job_id = None
    try:
        job_id = Request.scope.get('query_string') if False else None
    except Exception:
        job_id = None

    # Prefer to read a job doc if provided via query param `job_id`
    # Fast path: check for query param manually
    try:
        from fastapi import Request as _Request
        # attempt to access request from context
    except Exception:
        _Request = None

    # Try to read job_id from query parameters (safe fallback)
    # Note: FastAPI passes query params via request param, but this endpoint
    # has no Request object; instead allow callers to use /jobs/{job_id}.
    # Here we fallback to file-based counts.
    base = Path(__file__).parent.parent
    cand = base / 'data' / 'candidates.json'
    enriched = base / 'data' / 'enriched.jsonl'
    total = 0
    done = 0
    try:
        if cand.exists():
            with cand.open('r', encoding='utf-8') as f:
                arr = json.load(f)
                total = len(arr)
        if enriched.exists():
            with enriched.open('r', encoding='utf-8') as f:
                done = sum(1 for _ in f)
    except Exception:
        pass
    return {'total_candidates': total, 'enriched_count': done}


class GenerateRequest(BaseModel):
    message: str


@app.post('/generate')
async def generate_text(req: GenerateRequest):
    """Generate a response using available providers (best-effort).

    Falls back to an echo if providers are not configured.
    """
    try:
        from services.ai_providers import generate_text as gen_with_meta
        out = gen_with_meta(req.message)
        # gen_with_meta returns {'response': text, 'provider': name}
        if isinstance(out, dict):
            return {'response': out.get('response'), 'provider': out.get('provider')}
        return {'response': out, 'provider': 'unknown'}
    except Exception:
        return {'response': f"(local-echo) {req.message}", 'provider': 'local-echo'}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    doc = db.collection('jobs').document(job_id).get()
    if not doc.exists:
        return {"error": "job not found"}
    return doc.to_dict()


@app.get('/neo4j/graph')
async def get_neo4j_graph(limit: int = 1000):
    """Return a graph projection from Neo4j if configured."""
    if not neo4j_fetch:
        return JSONResponse({'error': 'Neo4j not configured'}, status_code=404)
    try:
        g = neo4j_fetch(limit=limit)
        return g
    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=500)


@app.get('/solidified_knowledge/{concept_id}')
async def get_solidified(concept_id: str):
    """Return the Firestore document for a finalized concept, or a 404."""
    try:
        doc = db.collection('solidified_knowledge').document(concept_id).get()
        if not doc.exists:
            return JSONResponse({'error': 'not found'}, status_code=404)
        return doc.to_dict()
    except Exception:
        # fallback: try to read from local data file if present
        base = Path(__file__).parent.parent
        solid = base / 'data' / 'enriched.jsonl'
        try:
            if solid.exists():
                with solid.open('r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            if entry.get('word') == concept_id:
                                return entry
                        except Exception:
                            continue
        except Exception:
            pass
        return JSONResponse({'error': 'not found'}, status_code=404)


@app.post('/reconcile/run')
async def run_reconcile():
    job_id = str(uuid.uuid4())
    try:
        db.collection('jobs').document(job_id).set({'status': 'queued', 'mode': 'reconcile', 'created_at': __import__('datetime').datetime.utcnow().isoformat()})
    except Exception:
        pass
    celery_app.send_task('api.tasks.reconcile_neo4j_firestore', args=[job_id])
    return {'status': 'queued', 'job_id': job_id}


class FinalizeRequest(BaseModel):
    concept_id: str


@app.post('/jobs/finalize')
async def finalize_job(req: FinalizeRequest):
    """Enqueue a finalize_concept Celery task for a concept id."""
    concept_id = req.concept_id
    job_id = str(uuid.uuid4())
    try:
        db.collection('jobs').document(job_id).set({
            'status': 'queued',
            'mode': 'finalize',
            'concept_id': concept_id,
            'created_at': __import__('datetime').datetime.utcnow().isoformat(),
            'progress': 0,
            'errors': []
        })
    except Exception:
        pass

    celery_app.send_task('api.tasks.finalize_concept', args=[concept_id, job_id])
    return {'status': 'queued', 'job_id': job_id}


@app.websocket("/ws/jobs/{job_id}")
async def websocket_job(websocket: WebSocket, job_id: str):
    await websocket.accept()
    try:
        while True:
            doc = db.collection('jobs').document(job_id).get()
            if doc.exists:
                await websocket.send_json(doc.to_dict())
                data = doc.to_dict()
                if data.get('status') in ('completed', 'failed'):
                    break
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
    finally:
        await websocket.close()
