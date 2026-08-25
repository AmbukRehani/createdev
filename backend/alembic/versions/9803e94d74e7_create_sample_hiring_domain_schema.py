"""create sample hiring domain schema

Revision ID: 9803e94d74e7
Revises: 90346af13ea5
Create Date: 2026-08-20 22:46:48.940538

Not part of DESIGN.md §5 — fixture data for the 3 seeded query_templates
to run against (candidates, jobs, applications, interviews).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9803e94d74e7'
down_revision: Union[str, Sequence[str], None] = '90346af13ea5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "candidates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("email", name="uq_candidates_email"),
    )

    op.create_table(
        "jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("department", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "status IN ('open', 'closed', 'on_hold')", name="ck_jobs_status"
        ),
    )
    op.create_index("ix_jobs_title", "jobs", ["title"])
    op.create_index("ix_jobs_department", "jobs", ["department"])

    op.create_table(
        "applications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.id"], name="fk_applications_candidate_id"
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name="fk_applications_job_id"
        ),
        sa.CheckConstraint(
            "stage IN ('applied', 'screen', 'interview', 'offer', 'hired', 'rejected')",
            name="ck_applications_stage",
        ),
        sa.CheckConstraint(
            "outcome IN ('hired', 'rejected', 'withdrawn')",
            name="ck_applications_outcome",
        ),
    )
    op.create_index("ix_applications_candidate_id", "applications", ["candidate_id"])
    op.create_index("ix_applications_job_id", "applications", ["job_id"])

    op.create_table(
        "interviews",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("round", sa.Text(), nullable=False),
        sa.Column("interviewer", sa.Text(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Numeric(3, 1), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_interviews_application_id",
        ),
        sa.CheckConstraint(
            "round IN ('phone_screen', 'technical', 'onsite', 'final')",
            name="ck_interviews_round",
        ),
        sa.CheckConstraint(
            "recommendation IN ('strong_yes', 'yes', 'no', 'strong_no')",
            name="ck_interviews_recommendation",
        ),
    )
    op.create_index("ix_interviews_application_id", "interviews", ["application_id"])


def downgrade() -> None:
    op.drop_index("ix_interviews_application_id", table_name="interviews")
    op.drop_table("interviews")

    op.drop_index("ix_applications_job_id", table_name="applications")
    op.drop_index("ix_applications_candidate_id", table_name="applications")
    op.drop_table("applications")

    op.drop_index("ix_jobs_department", table_name="jobs")
    op.drop_index("ix_jobs_title", table_name="jobs")
    op.drop_table("jobs")

    op.drop_table("candidates")
