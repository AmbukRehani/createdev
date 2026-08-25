import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LlmUsage(Base):
    """DESIGN.md §5 — one row per node invocation, not per request.

    cost_usd is computed once at call time (app/agents/llm.py) and stored
    here — a deliberate reversal of §5's original "derive cost at read
    time" note.
    """

    __tablename__ = "llm_usage"
    __table_args__ = (
        CheckConstraint("node IN ('understand', 'respond')", name="ck_llm_usage_node"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    # Indexed; joins to audit_trail.trace_id logically (DESIGN §5). Not a DB
    # FK: audit_trail.trace_id has no uniqueness constraint documented.
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    node: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), nullable=False, server_default="0"
    )
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
