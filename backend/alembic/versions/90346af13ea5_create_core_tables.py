"""create core tables

Revision ID: 90346af13ea5
Revises:
Create Date: 2026-08-20 22:46:48.722599

DESIGN.md §5 — query_templates, audit_trail, llm_usage.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '90346af13ea5'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "query_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("intent", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sql_text", sa.Text(), nullable=False),
        sa.Column("params_schema", postgresql.JSONB(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("intent", name="uq_query_templates_intent"),
    )

    op.create_table(
        "audit_trail",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("intent", sa.Text(), nullable=True),
        sa.Column(
            "params",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("route", sa.Text(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["intent"],
            ["query_templates.intent"],
            name="fk_audit_trail_intent_query_templates",
        ),
        sa.CheckConstraint(
            "route IN ('answer', 'clarified', 'error')", name="ck_audit_trail_route"
        ),
    )
    op.create_index("ix_audit_trail_trace_id", "audit_trail", ["trace_id"])
    op.create_index("ix_audit_trail_created_at", "audit_trail", ["created_at"])

    op.create_table(
        "llm_usage",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "node IN ('understand', 'respond')", name="ck_llm_usage_node"
        ),
    )
    op.create_index("ix_llm_usage_trace_id", "llm_usage", ["trace_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_usage_trace_id", table_name="llm_usage")
    op.drop_table("llm_usage")

    op.drop_index("ix_audit_trail_created_at", table_name="audit_trail")
    op.drop_index("ix_audit_trail_trace_id", table_name="audit_trail")
    op.drop_table("audit_trail")

    op.drop_table("query_templates")
