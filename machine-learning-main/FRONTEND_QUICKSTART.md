# Frontend Monitor - Quick Start Guide

## What's New 🎉

A complete real-time monitoring frontend for the 10-minute Big Learning Job has been built!

### Components Created

1. **`api/static/index.html`** - Beautiful, interactive web UI with:
   - 🎯 Start button for Big Learning Jobs
   - 📊 Real-time progress dashboard
   - 📈 Live metrics (rounds, tokens learned, progress %)
   - 📋 Event log with timestamps
   - ✨ WebSocket auto-reconnect logic
   - 👀 Responsive design (works on mobile too)

2. **Updated `api/app.py`** - FastAPI now:
   - Serves static files from `api/static/`
   - Routes `/` to the frontend HTML
   - Keeps all existing API endpoints

3. **Comprehensive `api/README.md`** - Full documentation including:
   - Architecture diagram
   - Step-by-step setup instructions
   - API endpoint reference
   - Troubleshooting guide
   - Performance notes

## Running Locally (End-to-End)

### Terminal 1: Start Redis (Message Broker)

```bash
docker run -d --name redis -p 6379:6379 redis:7
```

Or if Redis already running, skip this step.

### Terminal 2: Start Celery Worker (Background Jobs)

```bash
cd /workspaces/machinelearning/machine-learning-main
celery -A api.tasks.celery_app worker --loglevel=info
```

Wait for output like:
```
 -------------- celery@... v5...x.x ----
 --- * ***  * -- Linux...
```

### Terminal 3: Start FastAPI Server

```bash
cd /workspaces/machinelearning/machine-learning-main
uvicorn api.app:app --reload --port 8000
```

Wait for:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Terminal 4: Open Browser

Navigate to: **http://localhost:8000**

You should see the beautiful purple-themed UI with:
- "Start Big Learning Job" button
- "Reset" button
- Status panel (initially hidden)

## Using the Frontend

### Step 1: Click "Start Big Learning Job"

The button becomes disabled, and you'll see:
- Job ID appears in the status panel
- Status badge shows "QUEUED"
- Live events log starts: `[HH:MM:SS] ➜ Job created: ...`

### Step 2: Watch It Run

Every second, the WebSocket updates show:
- **🔄 Status**: Changes Queued → Running → Completed
- **📊 Progress**: Bar fills to 100%
- **🔢 Rounds**: Increments as each round completes
- **🎓 Tokens Learned**: Counts up (each token = 1 learned word)
- **📋 Events**: Live log showing:
  - Round start/end
  - Token discoveries
  - Errors (if any)

Example event log:
```
[10:30:45] ➜ Job created: 550e8400-...
[10:30:46] ✅ Connected to job stream
[10:30:47] ➜ Starting round 1 - generating tokens...
[10:31:02] ✅ Processed token: backpropagation
[10:31:15] ✅ Processed token: gradient descent
...
```

### Step 3: Job Completes (or times out at 10 min)

When done, you'll see:
- Status badge: "COMPLETED"
- Success message showing total tokens learned
- Button re-enables for new jobs

## Frontend Features

### 🎨 UI Components

- **Control Panel**: Start & Reset buttons
- **Status Grid**: Job ID, Status, Rounds, Tokens
- **Progress Bar**: 0-100% visual indicator
- **Info/Error Boxes**: Contextual messages
- **Live Event Log**: Scrollable terminal-style log
- **Responsive Design**: Works on desktop & mobile

### 🔄 WebSocket Auto-Reconnect

If connection drops:
- Automatically retries every 5 seconds
- Shows "Reconnecting..." log entry
- Resumes updates once connected

### 📱 Mobile Friendly

Grid layout adapts; progress bar and event log remain visible on smaller screens.

## Testing

### Quick Test (No Dependencies)

Open browser DevTools (F12) and manually test WebSocket:
```javascript
// In browser console:
const ws = new WebSocket('ws://localhost:8000/ws/jobs/test-id');
ws.onmessage = (msg) => console.log(JSON.parse(msg.data));
```

### Full Integration Test

1. Run all 3 servers (Redis, Celery, FastAPI)
2. Click "Start Big Learning Job"
3. Verify:
   - ✅ Job ID appears
   - ✅ Status changes to RUNNING within 2 seconds
   - ✅ Token counts increment
   - ✅ Log shows events every ~30 seconds
   - ✅ After 10 minutes: Status → COMPLETED

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Can't reach http://localhost:8000** | Check FastAPI is running in Terminal 3. Port 8000 accessible? |
| **"Connected" but no updates** | Verify Celery worker running (Terminal 2). Check logs for errors. |
| **Button disabled forever** | Check FastAPI logs for job creation errors. |
| **Progress stuck at 0%** | Celery task may not be picked up. Restart worker. |
| **Connection drops after 1 min** | Browser firewall? Check browser console for WebSocket errors. |

## Architecture Summary

```
User                Frontend (HTML/JS)              FastAPI               Celery
│                   ┌─────────────────┐            ┌──────────┐         ┌────────┐
├──── Click ──────→ │ Start Big Job   │ ──POST──→ │/jobs/    │ ──→ │run_big │
│                   │  Button         │           │start_big │ (queue) │learning│
│                   └─────────────────┘           └──────────┘       │ job    │
│                           │                                        └────────┘
│                           ↓ (connect WebSocket)                         │
│                   ┌─────────────────┐            ┌──────────┐          │
├── every 1s ←──── │ Update Progress │ ←─JSON─ │/ws/jobs/ │ ←───────┴────────┐
│                   │  Dashboard      │           │{job_id}  │ (from Firestore) │
│                   └─────────────────┘           └──────────┘                  │
└───────────────────────────────────────────────────────────────────────────────┘
```

## Next Steps (Optional Enhancements)

1. **Add Job History**: Store past job results, view in UI
2. **Cancel Button**: Stop running job via `DELETE /jobs/{job_id}`
3. **Export Results**: Download learned words as CSV/JSON
4. **Advanced Filters**: Show only completed jobs, errors, recent, etc.
5. **Admin Dashboard**: Monitor all jobs (not just current one)
6. **Cloud Deployment**: Run on Google Cloud Run + Cloud Tasks

## File Reference

| File | Purpose |
|------|---------|
| `api/app.py` | FastAPI server + WebSocket endpoints |
| `api/tasks.py` | Celery task definitions (run_big_learning_job) |
| `api/static/index.html` | Frontend UI (you are here) |
| `api/README.md` | Full technical documentation |
| `services/researcher.py` | Web search with fallbacks |
| `logic/advanced_learning.py` | Learning pipeline |
| `services/chroma_helper.py` | Vector DB (ChromaDB) |
| `brain/db.py` | Firestore initialization |

## Questions?

Check `api/README.md` for:
- Full API endpoint docs
- Environment variable setup
- Performance benchmarks
- Deployment guide
