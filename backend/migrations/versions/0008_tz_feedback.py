"""custom TZ feedback and AI-origin marker

Revision ID: 0008_tz_feedback
Revises: 0007_merge_heads
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0008_tz_feedback"
down_revision: Union[str, None] = "0007_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tz_documents",
        sa.Column("ai_initially_generated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "tz_documents",
        sa.Column("feedback", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("tz_documents", "feedback")
    op.drop_column("tz_documents", "ai_initially_generated")
