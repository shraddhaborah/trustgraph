"""FastAPI API layer.

Two invariants that fix the 500 / 504 / hang symptoms:

1. This process is a Temporal CLIENT ONLY. It never builds a Worker, never
   imports workflow definitions for execution, and therefore never triggers
   sandbox validation inside a request. A bad workflow can no longer kill uvicorn.

2. POST /api/ingest returns in milliseconds with a 202 and a workflow_id. It does
   NOT await the workflow result. The GitHub Codespaces proxy (and most load
   balancers) cut idle connections around 60s, which is what produced the
   504 Gateway Timeout -- a Claude extraction over a 40-page trust simply takes
   longer than the proxy will hold a socket open. The frontend polls instead.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from temporalio.client import Client, WorkflowExecutionStatus, WorkflowFailureError
from temporalio.service import RPCError

import config
from shared import IngestRequest

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api")

_client: Client | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """One Temporal client for the process lifetime. Reconnecting per request
    added ~100ms and leaked gRPC channels."""
    global _client
    try:
        _client = await Client.connect(config.TEMPORAL_ADDRESS, namespace=config.TEMPORAL_NAMESPACE)
        log.info("Temporal client connected: %s", config.TEMPORAL_ADDRESS)
    except Exception as e:  # noqa: BLE001
        # Start anyway so /api/health can report the problem instead of the
        # server refusing to boot.
        log.error("Could not connect to Temporal at %s: %s", config.TEMPORAL_ADDRESS, e)
        _client = None
    yield
    _client = None


app = FastAPI(title="TrustGraph Ingestion API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS or ["*"],
    allow_credentials=False,  # cannot be True alongside allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_client() -> Client:
    if _client is None:
        raise HTTPException(
            status_code=503,
            detail="Temporal is unreachable. Is `temporal server start-dev` running?",
        )
    return _client


@app.get("/api/health")
async def health() -> dict:
    return {
        "api": "ok",
        "temporal_connected": _client is not None,
        "anthropic_key_loaded": bool(config.ANTHROPIC_API_KEY),
        "demo_mode": config.DEMO_MODE,
        "model": config.ANTHROPIC_MODEL,
        "task_queue": config.TASK_QUEUE,
    }


@app.post("/api/ingest", status_code=202)
async def ingest_pdf(file: UploadFile = File(...)) -> dict:
    # Validate the upload BEFORE touching Temporal: a malformed file is a 400
    # whether or not the workflow engine happens to be up.
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf uploads are accepted.")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(pdf_bytes) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )
    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File is not a valid PDF.")

    client = _require_client()

    document_id = str(uuid.uuid4())
    staged = config.UPLOAD_DIR / f"{document_id}.pdf"
    staged.write_bytes(pdf_bytes)  # stage on disk; keep bytes out of workflow history

    workflow_id = f"trust-ingestion-{document_id}"
    try:
        await client.start_workflow(
            "TrustIngestionWorkflow",
            IngestRequest(
                document_id=document_id, pdf_path=str(staged), filename=file.filename or "upload.pdf"
            ),
            id=workflow_id,
            task_queue=config.TASK_QUEUE,
        )
    except RPCError as e:
        staged.unlink(missing_ok=True)
        raise HTTPException(status_code=502, detail=f"Temporal rejected the workflow: {e}") from e

    log.info("Started %s for %s", workflow_id, file.filename)
    return {"workflow_id": workflow_id, "document_id": document_id, "status": "running"}


@app.get("/api/ingest/{workflow_id}")
async def get_status(workflow_id: str) -> dict:
    """Poll this. Returns quickly whether or not the workflow has finished."""
    client = _require_client()
    handle = client.get_workflow_handle(workflow_id)

    try:
        desc = await handle.describe()
    except RPCError as e:
        raise HTTPException(status_code=404, detail=f"Unknown workflow {workflow_id}: {e}") from e

    if desc.status == WorkflowExecutionStatus.RUNNING:
        detail = {"status": "running"}
        try:
            detail |= await handle.query("status")  # live progress from the workflow
        except Exception:  # noqa: BLE001
            pass  # worker may not have picked it up yet
        return {"workflow_id": workflow_id, **detail}

    if desc.status == WorkflowExecutionStatus.COMPLETED:
        return {"workflow_id": workflow_id, "status": "completed", "result": await handle.result()}

    try:
        await handle.result()
    except WorkflowFailureError as e:
        cause = e.cause
        return {
            "workflow_id": workflow_id,
            "status": "failed",
            "error": str(getattr(cause, "message", cause) or e),
            "error_type": getattr(cause, "type", None),
        }
    return {"workflow_id": workflow_id, "status": str(desc.status)}
