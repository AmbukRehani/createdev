"""GET /api/v1/traces/{trace_id} response contract."""
from uuid import UUID

from pydantic import BaseModel


class TraceCallEntry(BaseModel):
    node: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: int


class TraceResponse(BaseModel):
    trace_id: UUID
    question: str
    route: str
    confidence: float
    total_cost_usd: float
    total_latency_ms: int
    calls: list[TraceCallEntry]
