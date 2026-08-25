"""All models must be imported here so Base.metadata is complete for
Alembic autogeneration and for create_all-style tooling."""
from app.models.application import Application
from app.models.audit_trail import AuditTrail
from app.models.base import Base
from app.models.candidate import Candidate
from app.models.interview import Interview
from app.models.job import Job
from app.models.llm_usage import LlmUsage
from app.models.query_template import QueryTemplate

__all__ = [
    "Base",
    "QueryTemplate",
    "AuditTrail",
    "LlmUsage",
    "Candidate",
    "Job",
    "Application",
    "Interview",
]
