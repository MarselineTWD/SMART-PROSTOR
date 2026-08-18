"""tz_documents.storage_key — ссылка на docx в MinIO

Revision ID: 0006_storage_key
Revises: 0005_normative
Create Date: 2026-08-18 00:00:00

Добавляет колонку `storage_key` — ключ объекта в S3-бакете
`prostor-tz`. После экспорта docx-файл заливается в MinIO, а
дальнейшие скачивания идут через presigned URL.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0006_storage_key"
down_revision: Union[str, None] = "0005_normative"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tz_documents",
        sa.Column("storage_key", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tz_documents", "storage_key")
