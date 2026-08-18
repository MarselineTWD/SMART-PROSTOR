"""normative acts catalog + per-template links

Revision ID: 0005_normative
Revises: 0004_main_catalog
Create Date: 2026-08-18 00:00:00

Создаёт справочник нормативно-правовых актов (``normative_acts``) и
связочную таблицу (``template_normative_acts``). Наполняет обе из
``backend/app/data/normative_acts_seed.json`` (получен из docx-шаблонов
скриптом ``backend.app.scripts.extract_normative_acts``).

Эмбеддинги на актах наполняются лениво скриптом
``backend.app.scripts.embed_seeds`` на старте контейнера — так тяжёлая
ML-обвязка не нужна для применения миграции.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector


revision: str = "0005_normative"
down_revision: Union[str, None] = "0004_main_catalog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMB_DIM = 384
SEED_PATH = (
    Path(__file__).resolve().parents[2] / "app" / "data" / "normative_acts_seed.json"
)


def _to_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def upgrade() -> None:
    op.create_table(
        "normative_acts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("document_type", sa.String(), nullable=False, server_default="Прочее"),
        sa.Column("authority", sa.String(), nullable=True),
        sa.Column("number", sa.String(), nullable=True),
        sa.Column("date_issued", sa.Date(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("short_title", sa.String(), nullable=False, server_default=""),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("embedding", Vector(EMB_DIM), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "template_normative_acts",
        sa.Column("template_key", sa.String(), nullable=False),
        sa.Column(
            "act_id",
            sa.String(),
            sa.ForeignKey("normative_acts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("template_key", "act_id", name="pk_template_normative_acts"),
    )

    op.create_index(
        "ix_template_normative_acts_key",
        "template_normative_acts",
        ["template_key"],
    )

    op.execute(
        "CREATE INDEX ix_normative_acts_embedding_hnsw "
        "ON normative_acts USING hnsw (embedding vector_cosine_ops)"
    )

    _seed()


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_normative_acts_embedding_hnsw")
    op.drop_index("ix_template_normative_acts_key", table_name="template_normative_acts")
    op.drop_table("template_normative_acts")
    op.drop_table("normative_acts")


def _seed() -> None:
    if not SEED_PATH.exists():
        return
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))

    acts = sa.table(
        "normative_acts",
        sa.column("id", sa.String()),
        sa.column("document_type", sa.String()),
        sa.column("authority", sa.String()),
        sa.column("number", sa.String()),
        sa.column("date_issued", sa.Date()),
        sa.column("title", sa.Text()),
        sa.column("short_title", sa.String()),
        sa.column("url", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        acts,
        [
            {
                "id": a["id"],
                "document_type": a.get("document_type") or "Прочее",
                "authority": a.get("authority"),
                "number": a.get("number"),
                "date_issued": _to_date(a.get("date_issued")),
                "title": a["title"],
                "short_title": a.get("short_title") or a["title"][:120],
                "url": a.get("url"),
                "is_active": True,
            }
            for a in data.get("acts", [])
        ],
    )

    links = sa.table(
        "template_normative_acts",
        sa.column("template_key", sa.String()),
        sa.column("act_id", sa.String()),
        sa.column("sort_order", sa.Integer()),
    )
    op.bulk_insert(
        links,
        [
            {
                "template_key": link["template_key"],
                "act_id": link["act_id"],
                "sort_order": int(link.get("sort_order") or 0),
            }
            for link in data.get("template_links", [])
        ],
    )
