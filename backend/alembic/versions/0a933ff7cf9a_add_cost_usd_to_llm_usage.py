"""add cost_usd to llm_usage

Revision ID: 0a933ff7cf9a
Revises: 9803e94d74e7
Create Date: 2026-08-20 23:43:51.229116

Reverses DESIGN.md §5's original "cost deliberately excluded, derive at
read time" decision: cost is now computed once at call time (in
app/agents/llm.py) and stored, never derived later.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0a933ff7cf9a'
down_revision: Union[str, Sequence[str], None] = '9803e94d74e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "llm_usage",
        sa.Column(
            "cost_usd",
            sa.Numeric(10, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("llm_usage", "cost_usd")
