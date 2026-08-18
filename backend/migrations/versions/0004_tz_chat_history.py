"""tz documents chat history

Revision ID: 0004_tz_chat
Revises: 0003_procurement
Create Date: 2026-08-18 12:00:00

Добавляет колонку ``chat`` (JSON) в таблицу ``tz_documents`` для хранения
истории диалога с ИИ-ассистентом вместе с извлечёнными правками полей ТЗ.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_tz_chat"
down_revision: Union[str, None] = "0003_procurement"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tz_documents",
        sa.Column("chat", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("tz_documents", "chat")
