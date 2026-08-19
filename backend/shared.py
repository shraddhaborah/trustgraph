"""Dataclasses shared between the workflow and its activities.

This module must stay dependency-free (stdlib only). It is imported *inside* the
Temporal sandbox, so anything that pulls in httpx/urllib/requests here would
re-introduce the RestrictedWorkflowAccessError.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IngestRequest:
    """Workflow argument. Note: a PATH, never the PDF bytes."""

    document_id: str
    pdf_path: str
    filename: str


@dataclass
class ExtractParams:
    text: str
    chunk_index: int
    chunk_total: int


@dataclass
class ExtractedGraph:
    trust_name: str | None = None
    trust_type: str | None = None
    execution_date: str | None = None
    governing_law: str | None = None
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    provisions: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class TrustGraph:
    document_id: str
    filename: str
    trust_name: str | None = None
    trust_type: str | None = None
    execution_date: str | None = None
    governing_law: str | None = None
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    provisions: list[dict[str, Any]] = field(default_factory=list)
    chunks_processed: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "trust_name": self.trust_name,
            "trust_type": self.trust_type,
            "execution_date": self.execution_date,
            "governing_law": self.governing_law,
            "nodes": self.nodes,
            "edges": self.edges,
            "provisions": self.provisions,
            "stats": {
                "chunks_processed": self.chunks_processed,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
            },
        }