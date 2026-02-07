# FastAPI + Celery + WebSocket Learning Pipeline

Real-time monitoring and background job processing for the AI learning system.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Web Browser (Frontend)                       │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  HTML/JS UI:                                               │ │
│  │  - Start Big Learning Job (POST /jobs/start_big)           │ │
│  │  - Monitor Progress (GET /jobs/{job_id})                   │ │
│  │  - Stream Updates (WebSocket /ws/jobs/{job_id})            │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
              ↓ REST/WebSocket                      ↓
┌─────────────────────────────────────────────────────────────────┐
│                  FastAPI Server (Port 8000)                      │
│  - Route: POST /jobs/start_big                                  │
│  - Route: GET /jobs/{job_id}                                    │
│  - WebSocket: /ws/jobs/{job_id}                                 │
│  - Static: /static/index.html                                   │
└─────────────────────────────────────────────────────────────────┘
              ↓ Job Queue                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                 Celery Worker Pool                               │
│  - Task: run_learning_job() - quick/deep learning               │
│  - Task: run_big_learning_job() - 10-min tokenization job       │
│  - Broker: Redis (redis://localhost:6379)                       │
└─────────────────────────────────────────────────────────────────┘
              ↓ Persistence                        ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Firestore (GCP)                                │
│  Collections:                                                    │
│  - jobs/{job_id} - job status, progress                         │
│  - known_words/* - learned words + explanations                 │
│  - solidified_knowledge/* - enriched multidimensional data      │
│  - raw_training/{job_id}/rounds - tokenization logs             │
└─────────────────────────────────────────────────────────────────┘
```

## Setup (Local Development)

### Prerequisites
- Python 3.8+
- Docker (for Redis) or Redis installed locally
- Google Cloud credentials (GOOGLE_APPLICATION_CREDENTIALS)

### Step 1: Start Redis Broker

```bash
# Option A: Docker
docker run -d --name redis -p 6379:6379 redis:7

# Option B: Use existing Redis
# (ensure accessible at localhost:6379)
```

### Step 2: Start Celery Worker

Open a new terminal and run:

```bash
cd /path/to/repo
celery -A api.tasks.celery_app worker --loglevel=info
```

Expected output:
```
 -------------- celery@hostname v5.x.x ----
 ---- **** -----
 --- * ***  * -- Linux-x.y.z-x86_64
-- * - **** ---
 - ** ---------- [config]
 - ** ---------- [queues]
 - ** ---------- [app]
```

### Step 3: Start FastAPI Server

Open a new terminal and run:

```bash
cd /path/to/repo
uvicorn api.app:app --reload --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### Step 4: Open Frontend

Navigate to `http://localhost:8000` in your browser. You should see:
- **Start Big Learning Job** button
- Real-time job monitoring dashboard
- Live event log with timestamps

## Usage

### Via Web UI (Recommended)

1. Click **"Start Big Learning Job"**
2. Watch the dashboard update:
   - Job ID appears
   - Status badge changes: Queued → Running → Completed/Failed
   - Progress bar fills (0-100%)
   - Tokens learned counter increments
   - Live event log shows per-token processing
3. After 10 minutes or task completion, review results

### Via cURL (REST API)

**Start Big Learning Job:**
```bash
curl -X POST "http://localhost:8000/jobs/start_big" \
  -H "Content-Type: application/json"

# Response:
# {"job_id": "550e8400-e29b-41d4-a716-446655440000"}
```

**Query Job Status:**
```bash
curl "http://localhost:8000/jobs/550e8400-e29b-41d4-a716-446655440000"

# Response example:
# {
#   "job_id": "550e8400-e29b-41d4-a716-446655440000",
#   "status": "running",
#   "mode": "big",
#   "progress": 45,
#   "total_tokens": 120,
#   "last_round": 3,
#   "errors": []
# }
```

## API Endpoints

### `POST /jobs/start`
Start a quick or deep learning job (existing learning pipeline).

**Request:**
```json
{ "mode": "quick" }  // or "deep"
```

**Response:**
```json
{ "job_id": "..." }
```

### `POST /jobs/start_big`
Start the 10-minute raw-data big learning job.

**Response:**
```json
{ "job_id": "..." }
```

### `GET /jobs/{job_id}`
Fetch current job status.

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "mode": "big",
  "progress": 0-100,
  "total_tokens": 150,
  "last_round": 2,
  "created_at": "2024-01-15T10:30:00",
  "errors": []
}
```

### `WebSocket /ws/jobs/{job_id}`
Stream live job updates (1/sec).

**Message Format (JSON):**
```json
{
  "job_id": "...",
  "status": "running",
  "progress": 45,
  "total_tokens": 120,
  "last_round": 3,
  "errors": []
}
```

## Job Lifecycle

### Big Learning Job Stages

1. **Round Generation** (1000 words/round via Groq LLM)
   - Tokenize candidates
   - Dedup against `processed_tokens`
   - Skip if `is_known()`
   - Loop max 200 tokens/round
   
2. **Research & Synthesis**
   - `quick_research(word)` → web search
   - Groq synthesis → definition
   - Store to `known_words` collection

3. **Enrichment**
   - Groq enrichment prompt → multidimensional JSON
   - Fields: definition, related_concepts, examples, category
   - Store to `solidified_knowledge` collection

4. **Hard Stop** (10 minutes wall clock)
   - Task exits gracefully
   - Status → "completed"
   - Stores final round count, token count, progress %

## File Structure

```
api/
├── app.py              # FastAPI server + WebSocket endpoints
├── tasks.py            # Celery task definitions
├── static/
│   └── index.html      # Frontend HTML/JS UI
└── README.md           # This file
```

## Troubleshooting

### Issue: WebSocket connection fails
**Solution:** Ensure FastAPI is running on port 8000 and CORS is allowed.

### Issue: Celery worker not processing tasks
**Solution:** Check Redis is running (`docker ps | grep redis`). Restart worker if needed.

### Issue: Jobs never complete
**Solution:** Check `/ws/jobs/{job_id}` for error messages. Verify:
- Firestore credentials (GOOGLE_APPLICATION_CREDENTIALS)
- Groq API key configured
- Redis broker connectivity

### Issue: Progress stuck at 0%
**Solution:** Check Celery worker logs for exceptions. Ensure LLM API keys are valid.

## Performance Notes

- **Big Learning Job:** 1000 words/round, ~200 tokens/round processed, 10-minute max
- **Round Duration:** ~30-60 sec (dependent on LLM/research latency)
- **Expected Output:** 100-300 enriched knowledge entries per job run
- **WebSocket Update Frequency:** 1 update/second

## Environment Variables

Set these before running:

```bash
export CELERY_BROKER_URL="redis://localhost:6379/0"
export GROQ_API_KEY="gsk_..."
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/firestore-key.json"
```

## Next Steps

- [ ] Deploy to cloud (Cloud Run + Cloud Tasks instead of Celery)
- [ ] Add job persistence/retry logic
- [ ] Implement job cancellation endpoint
- [ ] Add rate limiting to prevent abuse
- [ ] Create admin dashboard for all jobs
- [ ] Integrate with CI/CD for automated testing
