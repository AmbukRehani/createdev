"""Sample hiring-domain schema — see candidate.py for why this exists and
why it has no repository."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Interview(Base):
    __tablename__ = "interviews"
    __table_args__ = (
        CheckConstraint(
            "round IN ('phone_screen', 'technical', 'onsite', 'final')",
            name="ck_interviews_round",
        ),
        CheckConstraint(
            "recommendation IN ('strong_yes', 'yes', 'no', 'strong_no')",
            name="ck_interviews_recommendation",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id"), nullable=False, index=True
    )
    round: Mapped[str] = mapped_column(Text, nullable=False)
    interviewer: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    score: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    # NULL while the interview hasn't been scored yet.
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
