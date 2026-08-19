"""Activities -- ALL I/O lives here.

Nothing in this module is imported by workflow.py at module scope in a way that
runs inside Temporal's sandbox. The workflow refers to these activities through
the shared dataclasses in `shared.py` plus `workflow.execute_activity`, so the
sandbox never has to import `anthropic` / `httpx` / `pypdf` at all.

That is the real fix for:
    RestrictedWorkflowAccessError: Cannot access urllib.request.Request.__mro_entries__
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

import anthropic
from pypdf import PdfReader
from temporalio import activity
from temporalio.exceptions import ApplicationError

import config
from shared import ExtractParams, ExtractedGraph, TrustGraph

log = logging.getLogger(__name__)

# Reuse one client across activity executions -- creating an httpx pool per call
# is a real source of latency and socket exhaustion under load.
_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        if not config.ANTHROPIC_API_KEY:
            # Non-retryable: retrying a missing key 3 times just wastes 30 seconds
            # and buries the real cause under generic "activity failed" noise.
            raise ApplicationError(
                "ANTHROPIC_API_KEY is not set. Put it in backend/.env and restart the worker.",
                type="ConfigurationError",
                non_retryable=True,
            )
        _client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=2)
    return _client


# --------------------------------------------------------------------------- #
# Activity 1: PDF -> text
# --------------------------------------------------------------------------- #
@activity.defn
async def extract_pdf_text_activity(pdf_path: str) -> str:
    """Read the staged PDF off disk and return its text.

    pypdf is synchronous and CPU-bound, so it runs in a thread -- blocking the
    activity's event loop starves heartbeats and the worker's task pollers.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise ApplicationError(
            f"Staged upload missing at {pdf_path}", type="MissingUpload", non_retryable=True
        )

    def _read() -> str:
        reader = PdfReader(str(path))
        pages = []
        for i, page in enumerate(reader.pages):
            pages.append(f"\n--- PAGE {i + 1} ---\n{page.extract_text() or ''}")
        return "".join(pages)

    text = await asyncio.to_thread(_read)
    text = re.sub(r"[ \t]+", " ", text).strip()

    if len(text) < 50:
        # Almost always a scanned/image-only PDF. Fail loudly rather than sending
        # an empty prompt to the model and getting a confidently empty graph back.
        raise ApplicationError(
            "No extractable text found -- this looks like a scanned PDF. Run OCR "
            "(e.g. ocrmypdf) before ingesting.",
            type="NoExtractableText",
            non_retryable=True,
        )

    activity.logger.info("Extracted %d chars from %s", len(text), path.name)
    return text


# --------------------------------------------------------------------------- #
# Activity 2: text chunk -> structured graph, via Claude
# --------------------------------------------------------------------------- #
_SYSTEM_PROMPT = """You are a trust and estate document analyst. You read trust \
instruments (ILITs, revocable living trusts, GRATs, dynasty trusts) and extract \
the parties and relationships as a graph.

Return ONLY a JSON object. No prose, no markdown fences.

Schema:
{
  "trust_name": string | null,
  "trust_type": string | null,
  "execution_date": string | null,
  "governing_law": string | null,
  "nodes": [
    {"id": string, "label": string,
     "type": "grantor"|"trustee"|"successor_trustee"|"beneficiary"|"contingent_beneficiary"|"trust"|"entity"|"asset"|"other",
     "attributes": object}
  ],
  "edges": [
    {"source": string, "target": string, "relationship": string, "evidence": string}
  ],
  "provisions": [{"title": string, "summary": string, "article": string | null}]
}

Rules:
- Node ids are stable slugs derived from the label (e.g. "jane_a_doe").
- "evidence" is a short quote (<= 15 words) from the document supporting the edge.
- Extract only what the text states. Do not infer parties who are not named.
- If a field is absent, use null or an empty list. Never invent values."""


def _tool_schema() -> dict:
    """Forcing a tool call is far more reliable than asking for raw JSON."""
    return {
        "name": "emit_trust_graph",
        "description": "Emit the extracted trust graph.",
        "input_schema": {
            "type": "object",
            "properties": {
                "trust_name": {"type": ["string", "null"]},
                "trust_type": {"type": ["string", "null"]},
                "execution_date": {"type": ["string", "null"]},
                "governing_law": {"type": ["string", "null"]},
                "nodes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "label": {"type": "string"},
                            "type": {"type": "string"},
                            "attributes": {"type": "object"},
                        },
                        "required": ["id", "label", "type"],
                    },
                },
                "edges": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string"},
                            "target": {"type": "string"},
                            "relationship": {"type": "string"},
                            "evidence": {"type": "string"},
                        },
                        "required": ["source", "target", "relationship"],
                    },
                },
                "provisions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "summary": {"type": "string"},
                            "article": {"type": ["string", "null"]},
                        },
                        "required": ["title", "summary"],
                    },
                },
            },
            "required": ["nodes", "edges"],
        },
    }


def _demo_graph(params: ExtractParams) -> ExtractedGraph:
    """Fixture used when DEMO_MODE is on. Exercises the entire pipeline -- workflow,
    activity dispatch, merging, persistence, rendering -- without an API key."""
    return ExtractedGraph(
        trust_name="The Jane A. Doe Irrevocable Life Insurance Trust",
        trust_type="ILIT (Irrevocable Life Insurance Trust)",
        execution_date="March 14, 2019",
        governing_law="State of New York",
        nodes=[
            {"id": "jane_a_doe", "label": "Jane A. Doe", "type": "grantor",
             "attributes": {"role": "Settlor and insured"}},
            {"id": "ilit", "label": "Doe ILIT", "type": "trust", "attributes": {}},
            {"id": "first_national", "label": "First National Trust Co.", "type": "trustee",
             "attributes": {"capacity": "Corporate trustee"}},
            {"id": "michael_doe", "label": "Michael Doe", "type": "successor_trustee",
             "attributes": {}},
            {"id": "sarah_doe", "label": "Sarah Doe", "type": "beneficiary",
             "attributes": {"relationship": "Daughter"}},
            {"id": "thomas_doe", "label": "Thomas Doe", "type": "beneficiary",
             "attributes": {"relationship": "Son"}},
            {"id": "doe_foundation", "label": "Doe Family Foundation",
             "type": "contingent_beneficiary", "attributes": {}},
            {"id": "policy", "label": "Term Life Policy #4471-B", "type": "asset",
             "attributes": {"face_value": "$2,000,000"}},
        ],
        edges=[
            {"source": "jane_a_doe", "target": "ilit", "relationship": "settles",
             "evidence": "Grantor hereby establishes this Trust"},
            {"source": "first_national", "target": "ilit", "relationship": "serves_as_trustee",
             "evidence": "shall serve as initial Trustee"},
            {"source": "michael_doe", "target": "first_national",
             "relationship": "succeeds_trustee", "evidence": "upon resignation of the Trustee"},
            {"source": "ilit", "target": "sarah_doe", "relationship": "distributes_to",
             "evidence": "in equal shares to the Grantor's children"},
            {"source": "ilit", "target": "thomas_doe", "relationship": "distributes_to",
             "evidence": "in equal shares to the Grantor's children"},
            {"source": "ilit", "target": "doe_foundation", "relationship": "remainder_to",
             "evidence": "if no issue survive"},
            {"source": "ilit", "target": "policy", "relationship": "owns",
             "evidence": "Trustee shall hold the Policy"},
        ],
        provisions=[
            {"title": "Crummey withdrawal rights",
             "summary": "Beneficiaries may withdraw contributions within 30 days of notice, "
                        "qualifying gifts for the annual exclusion.",
             "article": "IV"},
            {"title": "Spendthrift clause",
             "summary": "Beneficial interests cannot be assigned or reached by creditors "
                        "before distribution.",
             "article": "VII"},
            {"title": "Trustee removal",
             "summary": "A majority of adult beneficiaries may remove the corporate trustee "
                        "and appoint a successor.",
             "article": "IX"},
        ],
        input_tokens=0,
        output_tokens=0,
    )


@activity.defn
async def extract_trust_graph_activity(params: ExtractParams) -> ExtractedGraph:
    """Send one chunk of document text to Claude and get structured graph JSON back."""
    if config.DEMO_MODE:
        activity.logger.info("DEMO_MODE: returning fixture instead of calling Claude")
        await asyncio.sleep(1.5)  # make the progress bar visible
        return _demo_graph(params)

    client = _get_client()

    user_msg = (
        f"Document chunk {params.chunk_index + 1} of {params.chunk_total}.\n"
        f"Extract the trust graph from the text below.\n\n"
        f"<document>\n{params.text}\n</document>"
    )

    # Heartbeat so a hung model call is detected by Temporal instead of silently
    # eating the whole start_to_close timeout.
    async def _beat() -> None:
        while True:
            await asyncio.sleep(5)
            activity.heartbeat(f"waiting on model, chunk {params.chunk_index}")

    beat = asyncio.create_task(_beat())
    try:
        resp = await client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=config.MAX_OUTPUT_TOKENS,
            system=_SYSTEM_PROMPT,
            tools=[_tool_schema()],
            tool_choice={"type": "tool", "name": "emit_trust_graph"},
            messages=[{"role": "user", "content": user_msg}],
        )
    except anthropic.AuthenticationError as e:
        raise ApplicationError(
            f"Anthropic rejected the API key: {e}", type="AuthenticationError", non_retryable=True
        ) from e
    except anthropic.BadRequestError as e:
        raise ApplicationError(
            f"Malformed request to Anthropic: {e}", type="BadRequest", non_retryable=True
        ) from e
    # RateLimitError / APIConnectionError / 5xx propagate and Temporal retries them.
    finally:
        beat.cancel()

    payload = next((b.input for b in resp.content if b.type == "tool_use"), None)
    if payload is None:
        # Fallback: model answered in text despite tool_choice.
        raw = "".join(b.text for b in resp.content if b.type == "text")
        raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ApplicationError(f"Model returned unparseable output: {e}") from e

    return ExtractedGraph(
        trust_name=payload.get("trust_name"),
        trust_type=payload.get("trust_type"),
        execution_date=payload.get("execution_date"),
        governing_law=payload.get("governing_law"),
        nodes=payload.get("nodes") or [],
        edges=payload.get("edges") or [],
        provisions=payload.get("provisions") or [],
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
    )


# --------------------------------------------------------------------------- #
# Activity 3: persist + clean up
# --------------------------------------------------------------------------- #
@activity.defn
async def persist_graph_activity(graph: TrustGraph) -> str:
    """Write the finished graph to disk (swap for Postgres/Neo4j when ready)."""
    out = config.UPLOAD_DIR / f"{graph.document_id}.graph.json"

    def _write() -> None:
        out.write_text(json.dumps(graph.to_dict(), indent=2))

    await asyncio.to_thread(_write)
    activity.logger.info("Persisted graph -> %s", out)
    return str(out)


@activity.defn
async def cleanup_upload_activity(pdf_path: str) -> None:
    Path(pdf_path).unlink(missing_ok=True)