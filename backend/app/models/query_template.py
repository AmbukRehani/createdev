import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class QueryTemplate(Base):
    """DESIGN.md §5 — the only place SQL exists. Seeded/curated, never
    written by the model."""

    __tablename__ = "query_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    intent: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Named binds only (:since, :status); no string interpolation, no LIMIT.
    sql_text: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON Schema for the typed slots; bind names in sql_text must exactly
    # match this schema's property names (DESIGN §8 invariant).
    params_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
