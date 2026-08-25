"""Sample hiring-domain schema — see candidate.py for why this exists and
why it has no repository."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'closed', 'on_hold')", name="ck_jobs_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    title: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    department: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    # e.g. junior, mid, senior, staff
    level: Mapped[str] = mapped_column(Text, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
