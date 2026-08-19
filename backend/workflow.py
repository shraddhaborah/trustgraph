"""Workflow definition -- orchestration ONLY.

Hard rules enforced here:
  * No `anthropic`, `httpx`, `pypdf`, `requests`, or `os.getenv` at this level.
  * No `datetime.now()`, `random`, `uuid4` -- use workflow.now() / workflow.uuid4().
  * Activities are referenced by NAME (strings), so the sandbox never imports
    activities.py and therefore never touches urllib/httpx.

That last point is what actually fixes the original crash. Wrapping the anthropic
import in `imports_passed_through()` also silences the error, but it drags an HTTP
client into workflow scope, which is the thing Temporal is warning you about.
Referencing by name keeps the boundary clean.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

# Stdlib-only dataclasses -- safe inside the sandbox.
with workflow.unsafe.imports_passed_through():
    import config
    from shared import ExtractedGraph, ExtractParams, IngestRequest, TrustGraph

_PDF_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_attempts=3,
    non_retryable_error_types=["MissingUpload", "NoExtractableText"],
)

_MODEL_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=5,
    non_retryable_error_types=["ConfigurationError", "AuthenticationError", "BadRequest"],
)


def _chunk(text: str, size: int, overlap: int) -> list[str]:
    """Deterministic chunking -- same input always yields the same chunks, which
    matters because this runs inside workflow code and is replayed."""
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # Prefer a page boundary, then a paragraph break.
            for marker in ("\n--- PAGE", "\n\n"):
                cut = text.rfind(marker, start + size // 2, end)
                if cut != -1:
                    end = cut
                    break
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


@workflow.defn
class TrustIngestionWorkflow:
    def __init__(self) -> None:
        self._status = "queued"
        self._progress = 0.0

    # Lets the frontend poll real progress instead of staring at a spinner.
    @workflow.query
    def status(self) -> dict:
        return {"status": self._status, "progress": round(self._progress, 2)}

    @workflow.run
    async def run(self, req: IngestRequest) -> dict:
        self._status = "extracting_text"

        text: str = await workflow.execute_activity(
            "extract_pdf_text_activity",
            req.pdf_path,
            result_type=str,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_PDF_RETRY,
        )
        self._progress = 0.15

        chunks = _chunk(text, config.CHUNK_CHARS, config.CHUNK_OVERLAP_CHARS)
        self._status = f"analyzing ({len(chunks)} chunk(s))"

        graph = TrustGraph(document_id=req.document_id, filename=req.filename)
        seen_nodes: set[str] = set()
        seen_edges: set[tuple] = set()

        for i, chunk in enumerate(chunks):
            partial: ExtractedGraph = await workflow.execute_activity(
                "extract_trust_graph_activity",
                ExtractParams(text=chunk, chunk_index=i, chunk_total=len(chunks)),
                # REQUIRED when calling an activity by name: without result_type the
                # data converter returns a plain dict, not the dataclass, and every
                # attribute access below fails with AttributeError.
                result_type=ExtractedGraph,
                start_to_close_timeout=timedelta(minutes=5),
                heartbeat_timeout=timedelta(seconds=30),
                retry_policy=_MODEL_RETRY,
            )

            # Merge, de-duplicating across overlapping chunks.
            for node in partial.nodes:
                if node.get("id") and node["id"] not in seen_nodes:
                    seen_nodes.add(node["id"])
                    graph.nodes.append(node)
            for edge in partial.edges:
                key = (edge.get("source"), edge.get("target"), edge.get("relationship"))
                if all(key) and key not in seen_edges:
                    seen_edges.add(key)
                    graph.edges.append(edge)
            graph.provisions.extend(partial.provisions)

            graph.trust_name = graph.trust_name or partial.trust_name
            graph.trust_type = graph.trust_type or partial.trust_type
            graph.execution_date = graph.execution_date or partial.execution_date
            graph.governing_law = graph.governing_law or partial.governing_law
            graph.input_tokens += partial.input_tokens
            graph.output_tokens += partial.output_tokens
            graph.chunks_processed += 1

            self._progress = 0.15 + 0.75 * ((i + 1) / len(chunks))

        self._status = "persisting"
        await workflow.execute_activity(
            "persist_graph_activity",
            graph,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        # Best-effort cleanup; a leftover temp file must not fail the ingest.
        try:
            await workflow.execute_activity(
                "cleanup_upload_activity",
                req.pdf_path,
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
        except Exception:  # noqa: BLE001
            workflow.logger.warning("cleanup failed for %s", req.pdf_path)

        self._status = "completed"
        self._progress = 1.0
        return graph.to_dict()