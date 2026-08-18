"""merge TZ chat and database/storage migration branches

Revision ID: 0007_merge_heads
Revises: 0004_tz_chat, 0006_storage_key
Create Date: 2026-08-18 13:00:00
"""
from __future__ import annotations

from typing import Sequence, Union


revision: str = "0007_merge_heads"
down_revision: Union[str, tuple[str, str], None] = (
    "0004_tz_chat",
    "0006_storage_key",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
