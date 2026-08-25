"""Sample hiring-domain schema — NOT part of DESIGN.md §5. Exists only so
the 3 seeded query_templates have real tables/data to run against. No
repository is provided for this table: nothing in the app queries it via
the ORM, it's read only through curated template SQL at execution time
(the execution path itself is agent logic, out of scope for now).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # e.g. referral, job_board, linkedin, career_site, agency
    source: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
