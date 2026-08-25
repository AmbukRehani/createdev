"""LangGraph state for the two-node understand/respond flow (DESIGN §3)."""
from typing import Any, Literal, TypedDict
from uuid import UUID


class GraphState(TypedDict):
    trace_id: UUID
    question: str
    intent: str | None
    params: dict[str, Any]
    confidence: float
    route: Literal["answer", "clarified"] | None
    # Transient only — never logged whole or persisted (DESIGN §5/§7
    # exclude returned rows; only a row_count is ever recorded).
    rows: list[dict[str, Any]] | None
    answer: str | None
    clarification: str | None
