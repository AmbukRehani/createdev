"""POST /api/v1/query request/response contract.

DESIGN.md §6 documents two DISTINCT success shapes for this endpoint
(route=answer vs route=clarified) and never mentions a `usage` field —
that only appears on GET /v1/traces/{trace_id}. Per explicit instruction,
QueryResponse is instead one flat superset of both §6 variants plus a
`usage` list (a deliberate extension beyond §6 for this endpoint). Fields
that don't apply to a given `route` are null/empty rather than omitted.
This shape is final — only the values change once the agent nodes land.

Error responses do NOT use this model: they go through
app.core.errors' §6 error envelope via the exception handlers.
"""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    trace_id: UUID | None = None


class UsageEntry(BaseModel):
    """Mirrors an app_models.LlmUsage row (DESIGN §5)."""

    node: Literal["understand", "respond"]
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int


class QueryResponse(BaseModel):
    trace_id: UUID
    route: Literal["answer", "clarified"]

    # route=answer fields (DESIGN §6) — null when route=clarified
    answer: str | None = None
    intent: str | None = None
    params: dict = Field(default_factory=dict)
    row_count: int | None = None

    # route=clarified fields (DESIGN §6) — null/empty when route=answer
    clarifying_question: str | None = None
    candidate_intents: list[str] = Field(default_factory=list)

    # shared across both §6 variants
    confidence: float
    latency_ms: int

    # extension beyond §6 for this endpoint (explicit instruction)
    usage: list[UsageEntry] = Field(default_factory=list)
    cost_usd: float = 0.0
