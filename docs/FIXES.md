# TrustGraph ingestion — root causes and fixes

## The one-line diagnosis

The ingestion engine wasn't failing for five different reasons. It was failing for
**one architectural reason** that presented as five different symptoms: the FastAPI
process was trying to be the Temporal worker as well as the Temporal client.

```python
# main.py, inside the request handler — this was the bug
async with Worker(client, task_queue="trust-queue",
                  workflows=[TrustIngestionWorkflow], ...):
```

`Worker(...)` validates every workflow definition at construction time by executing
the module inside Temporal's determinism sandbox. Doing that per-HTTP-request means
any sandbox violation raises inside an ASGI task and takes uvicorn down with it —
which is why DevTools showed `0.0 kB transferred` and "No data found for resource":
the server died mid-response.

## Symptom → cause → fix

| Symptom you saw | Actual cause | Fix |
|---|---|---|
| `RestrictedWorkflowAccessError: Cannot access urllib.request.Request.__mro_entries__` | `from anthropic import Anthropic` at the top of the workflow module. `anthropic` → `httpx` → `urllib`, all banned in the sandbox | Activities moved to `activities.py`; the workflow calls them **by name string**, so the sandbox never imports them |
| `RuntimeError: Failed validating workflow` + uvicorn killed | `Worker()` built inside the route handler | `Worker` now exists only in `worker.py`, a separate long-lived process |
| 500 that disappeared and came back | `ANTHROPIC_API_KEY` exported into one terminal; a reloaded/other process didn't have it | `.env` + `python-dotenv` in `config.py`. No more terminal-scoped state |
| `[Errno 98] Address already in use` | Old uvicorn still bound to 8000 | `start-dev.sh` clears the port; also fixed by not needing constant restarts |
| Request to `...-5173.app.github.dev/api/ingest` → 500 | Vite had no `/api` route and no proxy | Proxy added in `vite.config.ts` |
| 401 Unauthorized | Codespaces reset port 8000 to Private; its auth proxy blocks cross-port fetches | Proxy keeps everything on origin 5173. Port 8000 can stay Private |
| Request hangs forever ("NOW IT DOES NOTHING") | `await client.execute_workflow(...)` blocks until completion, and no worker was polling `trust-queue` | `start_workflow` + polling; worker runs as its own process |
| 504 Gateway Timeout | Same blocking call — the Codespaces proxy cuts sockets at ~60s, and real extraction takes longer | `POST` returns **202 + workflow_id** in milliseconds; frontend polls `GET /api/ingest/{id}` |

## Beyond the crash — correctness issues that would have bitten next

- **Raw PDF bytes as a workflow argument.** Temporal caps payloads (~2 MB) and stores
  every argument in workflow history forever. A 5 MB trust document would have failed
  with an opaque error. Files are now staged on disk; the workflow receives a path.
- **No chunking.** A long trust instrument silently overflowed the prompt. Now chunked
  deterministically on page boundaries with overlap, then merged and de-duplicated.
- **Retrying unretryable errors.** A missing API key was retried until timeout, burying
  the cause. Config/auth/malformed-request errors are now `non_retryable`.
- **No heartbeat.** A hung model call consumed the full `start_to_close_timeout`.
  Activities heartbeat every 5s.
- **Blocking the event loop.** `pypdf` is sync and CPU-bound; it now runs in a thread.
- **Client per request.** The Anthropic client is created once and reused.
- **`allow_credentials=True` with `allow_origins=["*"]`** — an invalid CORS combination
  that browsers reject. Fixed.

## Architecture

```
Browser (5173) ──POST /api/ingest──▶ Vite proxy ──▶ FastAPI (8000)   [CLIENT ONLY]
       │                                                  │
       │                                        start_workflow (returns 202 immediately)
       │                                                  ▼
       │                                          Temporal (7233)
       │                                                  │
       │                                          trust-queue
       │                                                  ▼
       └──GET /api/ingest/{id} (poll)◀───────  worker.py  [ALL I/O LIVES HERE]
                                                  ├─ extract_pdf_text_activity  (pypdf)
                                                  ├─ extract_trust_graph_activity (Claude)
                                                  ├─ persist_graph_activity
                                                  └─ cleanup_upload_activity
```

**The rule to keep:** workflow code orchestrates and must be replayable. Anything that
touches the network, the filesystem, the clock, or randomness goes in an activity.

## Running it

```bash
cd backend
cp .env.example .env        # then paste your NEW key into .env
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

./start-dev.sh              # Temporal + worker + API in one shot
```

Or three terminals if you prefer to see each log stream:

```bash
temporal server start-dev                    # 1
cd backend && source venv/bin/activate && python worker.py    # 2
cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000   # 3
cd frontend && npm run dev                   # 4
```

## Verifying before you upload anything

```bash
curl localhost:8000/api/health
# {"api":"ok","temporal_connected":true,"anthropic_key_loaded":true,...}
```

If `anthropic_key_loaded` is false, your `.env` isn't being read. If
`temporal_connected` is false, the dev server isn't up. Both were previously
invisible until an upload failed with a 500.

Temporal's web UI at **http://localhost:8233** shows every workflow, its inputs, each
activity attempt, and the full failure stack — far better than reading DevTools.

## Security note

The API key that appeared in the debugging transcript must be revoked and reissued.
`.env` is gitignored; keep keys out of shell commands, which land in `~/.bash_history`
and in any screenshot of your terminal.
