"""The worker process. Run this in its own terminal:  python worker.py

A Worker is a long-lived polling process. It must NEVER be constructed inside a
FastAPI request handler -- that was the bug that hard-killed uvicorn: Worker()
validates every workflow definition at construction time, and a validation error
inside an ASGI task takes the server down with it.
"""

from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

import config
from activities import (
    cleanup_upload_activity,
    extract_pdf_text_activity,
    extract_trust_graph_activity,
    persist_graph_activity,
)
from workflow import TrustIngestionWorkflow

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("worker")


async def main() -> None:
    if not config.ANTHROPIC_API_KEY:
        log.error("ANTHROPIC_API_KEY is empty. Set it in backend/.env before starting the worker.")
        raise SystemExit(1)

    client = await Client.connect(config.TEMPORAL_ADDRESS, namespace=config.TEMPORAL_NAMESPACE)
    log.info("Connected to Temporal at %s", config.TEMPORAL_ADDRESS)

    worker = Worker(
        client,
        task_queue=config.TASK_QUEUE,
        workflows=[TrustIngestionWorkflow],
        activities=[
            extract_pdf_text_activity,
            extract_trust_graph_activity,
            persist_graph_activity,
            cleanup_upload_activity,
        ],
        max_concurrent_activities=8,
    )
    log.info("Worker polling task queue %r. Ctrl+C to stop.", config.TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Worker stopped.")