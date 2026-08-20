# trustgraph

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/shraddhaborah/trustgraph-)

> Click the badge, wait ~2 minutes, upload the sample PDF in `backend/sample_ilit_trust.pdf`.
> Runs in demo mode with no API key required — add one to `backend/.env` for real extraction.

<!-- Add a screenshot or GIF of the graph view here. It matters more than everything below. -->

Upload a trust document, get back a graph of who's who: gr<img width="1470" height="936" alt="Screenshot 2026-08-20 at 7 16 19 PM" src="https://github.com/user-attachments/assets/07de9f18-c232-4f98-be52-1b4df1119387" />
<img width="724" height="805" alt="Screenshot 2026-08-20 at 7 13 27 PM" src="https://github.com/user-attachments/assets/1e8485dc-f247-437c-8f74-bc79fcf3520e" />
<img width="689" height="862" alt="Screenshot 2026-08-20 at 7 15 13 PM" src="https://github.com/user-attachments/assets/ddbeac7f-e5b1-4f9c-8234-7a3788f97d5b" />
antors, trustees, beneficiaries, and the relationships between them. Claude does the extraction, Temporal handles the orchestration.

This started as a project to see whether an LLM could reliably pull structured relationships out of estate planning documents. Short answer: yes, if you give it a strict schema and stop asking it to return raw JSON.

<img width="718" height="693" alt="Screenshot 2026-08-20 at 7 12 32 PM" src="https://github.com/user-attachments/assets/fb84e6a5-7f48-4ccb-bce3-dbce34ce8614" />


## How it works

```
browser → FastAPI → Temporal → worker → Claude
                                      → graph JSON
```

FastAPI takes the upload, stages the PDF on disk, and starts a Temporal workflow. It returns a workflow ID immediately — it does not wait around. A separate worker process picks the job off the queue, extracts text with pypdf, sends it to Claude in chunks, merges the results, and writes out the graph. The frontend polls until it's done.

The split between the API and the worker isn't optional. Temporal runs workflow code in a sandbox that blocks anything non-deterministic, and that includes importing an HTTP client. Put your Claude calls in the workflow file and it won't even load. All network and filesystem work lives in `activities.py`; the workflow only orchestrates.

## Running it

You need Python 3.12, Node 18+, an Anthropic API key, and the Temporal CLI.

```bash
cd backend
cp .env.example .env        # add your key
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
./start-dev.sh
```

That script starts Temporal, the worker, and the API. Then in another terminal:

```bash
cd frontend && npm install && npm run dev
```

Open port 5173. Port 8000 doesn't need to be exposed — Vite proxies `/api` to it.

If you'd rather run the pieces separately there are four: `temporal server start-dev`, `python worker.py`, `uvicorn main:app --reload --port 8000`, and `npm run dev`. There's a VS Code task (`Ctrl+Shift+B`) that opens all four in labeled panes.

Before uploading anything, hit `curl localhost:8000/api/health`. Both `temporal_connected` and `anthropic_key_loaded` should be true. Saves finding out mid-upload.

## Layout

```
backend/
  main.py         FastAPI. Temporal client only — never constructs a Worker.
  worker.py       The worker process. Run separately.
  workflow.py     Orchestration. No network calls, no clock, no randomness.
  activities.py   PDF parsing and Claude calls live here.
  shared.py       Dataclasses passed between the two. Stdlib only.
  config.py       Reads .env once at import.
frontend/src/
  ingest.ts            Upload and polling.
  App.tsx              Dropzone, progress, error states.
  TrustGraphView.tsx   SVG diagram, no graph library.
```

## Things that cost me time

**Activities called by name need `result_type`.** Do `execute_activity("some_activity", ...)` with a string instead of the function reference and Temporal has no type information, so it hands back a plain dict. Attribute access on your dataclass then fails with a confusing `AttributeError`. Pass `result_type=YourClass`.

**The worker doesn't hot-reload.** `uvicorn --reload` picks up changes; `worker.py` doesn't. Edit an activity, forget to restart, and Temporal cheerfully replays the old code while you wonder why your fix didn't take.

**Don't pass file bytes as workflow arguments.** Temporal stores every argument in workflow history permanently and caps payloads around 2MB. Stage the file and pass a path.

**Long requests die at proxies, not at your server.** The first version awaited the workflow result inside the request handler. Fine locally, 504 through the Codespaces proxy, because extraction on a real document takes longer than 60 seconds. Return an ID and poll.

**Tool use beats "please return JSON."** Asking for raw JSON gets you markdown fences, preambles, and occasional prose. Defining a tool schema and forcing it with `tool_choice` gets a parsed dict every time. There's still a text-parsing fallback in `activities.py`, but it rarely fires.

## Debugging

The Temporal web UI on port 8233 is the thing to use. Every workflow, every activity attempt, actual inputs and outputs, full stack traces on failure. Substantially better than reading logs and much better than guessing from the browser's network tab.

Worker output goes to `/tmp/worker.log` when started via the script. Finished graphs land in `/tmp/trustgraph_uploads/*.graph.json`, which is how you tell a rendering problem from an extraction problem.

## Known gaps

- Graphs are written to local disk. Fine for a demo, needs a real database to be useful.
- Scanned PDFs fail with `NoExtractableText`. Run them through OCR first; there's no OCR step built in.
- No auth on any endpoint. Don't deploy this as-is.
- The extraction schema is tuned for ILITs and revocable living trusts. Other instrument types work, but the role taxonomy in the prompt may need extending.
- Chunk merging dedupes on node ID and edge triple. If Claude slugifies the same person differently across two chunks you get duplicates. Real entity resolution would fix it.

## Configuration

Everything lives in `.env`, with defaults in `config.py`. The ones worth knowing:

- `ANTHROPIC_MODEL` — defaults to `claude-sonnet-4-6`. Opus extracts better from dense legal language if you're willing to pay for it.
- `CHUNK_CHARS` — 60k characters per model call. Lower it to force multi-chunk behavior when testing the merge logic.
- `MAX_UPLOAD_BYTES` — 25MB.
