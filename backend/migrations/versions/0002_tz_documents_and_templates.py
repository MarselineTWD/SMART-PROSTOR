"""tz templates catalog and saved tz documents

Revision ID: 0002_tz
Revises: 0001_initial
Create Date: 2026-08-17 12:00:00

Создаёт таблицы каталога шаблонов ТЗ (``tz_templates``) и сохранённых
технических заданий (``tz_documents``) и наполняет каталог шаблонами из
``backend.app.data.tz_templates``. Это заменяет генерацию XLSX: результат
работы — сохранённое ТЗ, доступное на странице «Мои ТЗ».
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from backend.app.data.tz_templates import TZ_TEMPLATES


revision: str = "0002_tz"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tz_templates",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("stage_presets", sa.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "tz_documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("template_key", sa.String(), nullable=False),
        sa.Column("template_name", sa.String(), nullable=False, server_default=""),
        sa.Column("product_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False, server_default=""),
        sa.Column("object_name", sa.String(), nullable=True),
        sa.Column("customer_name", sa.String(), nullable=True),
        sa.Column("executor_name", sa.String(), nullable=True),
        sa.Column("contract_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("ready_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requisites", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("input_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("sections", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("notes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_index("ix_tz_documents_updated_at", "tz_documents", ["updated_at"])

    _seed_templates()


def downgrade() -> None:
    op.drop_index("ix_tz_documents_updated_at", table_name="tz_documents")
    op.drop_table("tz_documents")
    op.drop_table("tz_templates")


def _seed_templates() -> None:
    tz_templates = sa.table(
        "tz_templates",
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("product_id", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("stage_presets", sa.ARRAY(sa.String())),
        sa.column("fields", sa.JSON()),
        sa.column("sections", sa.JSON()),
        sa.column("sort_order", sa.Integer()),
    )

    rows = [
        {
            "key": tpl["key"],
            "name": tpl["name"],
            "product_id": tpl["product_id"],
            "description": tpl["description"],
            "stage_presets": list(tpl["stage_presets"]),
            "fields": tpl["fields"],
            "sections": tpl["sections"],
            "sort_order": index,
        }
        for index, tpl in enumerate(TZ_TEMPLATES)
    ]
    op.bulk_insert(tz_templates, rows)
