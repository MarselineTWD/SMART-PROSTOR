"""initial schema and seed

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-17 00:00:00

Creates pgvector extension, all core tables with vector(384) columns,
HNSW cosine indexes and seeds the MVP catalog. Embeddings are left NULL
here — they are computed by `backend.app.scripts.embed_seeds` after the
migration runs, so heavy ML dependencies stay out of the migration path.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EMB_DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "companies",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("rating", sa.Float(), nullable=False, server_default="0"),
        sa.Column("subcontract_policy", sa.String(), nullable=False, server_default="allowed"),
        sa.Column("embedding", Vector(EMB_DIM), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("keywords", sa.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("operations", sa.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("synonyms", sa.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("template_id", sa.String(), nullable=True),
        sa.Column("has_price_rules", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("has_operations", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_legacy", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("embedding", Vector(EMB_DIM), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "contracts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("product_ids", sa.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "historical_cases",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "product_id",
            sa.String(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.String(),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("object_name", sa.String(), nullable=False, server_default=""),
        sa.Column("embedding", Vector(EMB_DIM), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "intent_prompts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("intent", sa.String(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMB_DIM), nullable=True),
    )

    op.execute(
        "CREATE INDEX ix_products_embedding_hnsw "
        "ON products USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_historical_cases_embedding_hnsw "
        "ON historical_cases USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_intent_prompts_embedding_hnsw "
        "ON intent_prompts USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_companies_embedding_hnsw "
        "ON companies USING hnsw (embedding vector_cosine_ops)"
    )

    _seed()


def downgrade() -> None:
    op.drop_table("intent_prompts")
    op.drop_table("historical_cases")
    op.drop_table("contracts")
    op.drop_table("products")
    op.drop_table("companies")


def _seed() -> None:
    companies = sa.table(
        "companies",
        sa.column("id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("rating", sa.Float()),
        sa.column("subcontract_policy", sa.String()),
    )

    op.bulk_insert(
        companies,
        [
            {
                "id": "company-hantos",
                "name": "Хантос",
                "description": "Сильный подрядчик по геологии и оценке запасов.",
                "rating": 4.8,
                "subcontract_policy": "limit_70",
            },
            {
                "id": "company-megion",
                "name": "Мегионнефтегаз",
                "description": "Исполнитель со строгими правилами по субподряду.",
                "rating": 4.4,
                "subcontract_policy": "forbidden",
            },
            {
                "id": "company-angara",
                "name": "Ангара",
                "description": "Исполнитель по концептам развития и обустройства.",
                "rating": 4.2,
                "subcontract_policy": "separate_rs_required",
            },
        ],
    )

    products = sa.table(
        "products",
        sa.column("id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("summary", sa.Text()),
        sa.column("keywords", sa.ARRAY(sa.String())),
        sa.column("operations", sa.ARRAY(sa.String())),
        sa.column("synonyms", sa.ARRAY(sa.String())),
        sa.column("template_id", sa.String()),
        sa.column("has_price_rules", sa.Boolean()),
        sa.column("has_operations", sa.Boolean()),
        sa.column("is_legacy", sa.Boolean()),
    )

    op.bulk_insert(
        products,
        [
            {
                "id": "product-reserves",
                "name": "Подсчёт запасов / ПТД",
                "summary": "Оценка запасов по объекту с подготовкой ТЗ, этапов и пакета расчётов.",
                "keywords": ["запасы", "птд", "геология", "оценка", "подсчёт"],
                "operations": [
                    "сбор исходных данных",
                    "геологический анализ",
                    "расчёт запасов",
                    "подготовка отчёта",
                ],
                "synonyms": ["оценить запасы", "подсчет запасов", "reserves"],
                "template_id": "template-reserves",
                "has_price_rules": True,
                "has_operations": True,
                "is_legacy": False,
            },
            {
                "id": "product-geology",
                "name": "Концепт геологии",
                "summary": "Подготовка геологической концепции для новых и действующих объектов.",
                "keywords": ["геология", "геологический концепт", "модель", "скважина"],
                "operations": ["сбор геоданных", "интерпретация", "подготовка концепции"],
                "synonyms": ["геологический концепт", "концепция геологии"],
                "template_id": "template-geology",
                "has_price_rules": True,
                "has_operations": True,
                "is_legacy": False,
            },
            {
                "id": "product-concept",
                "name": "Концепт обустройства",
                "summary": "Разработка концепта обустройства объекта с вариантной проработкой.",
                "keywords": ["обустройство", "объект", "3d", "инфраструктура", "варианты"],
                "operations": [
                    "сбор требований",
                    "вариантное проектирование",
                    "3D-модель",
                    "календарный план",
                ],
                "synonyms": ["обустройство", "концепт объекта"],
                "template_id": "template-concept",
                "has_price_rules": True,
                "has_operations": True,
                "is_legacy": False,
            },
            {
                "id": "product-development",
                "name": "Интегрированный концепт развития",
                "summary": "Комплексная проработка развития актива с несколькими сценариями.",
                "keywords": ["развитие", "сценарий", "актив", "интегрированный концепт"],
                "operations": ["стратегическая сессия", "проектирование сценариев", "оценка эффектов"],
                "synonyms": ["концепт развития", "стратегия развития"],
                "template_id": "template-development",
                "has_price_rules": True,
                "has_operations": True,
                "is_legacy": False,
            },
        ],
    )

    contracts = sa.table(
        "contracts",
        sa.column("id", sa.String()),
        sa.column("company_id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("product_ids", sa.ARRAY(sa.String())),
    )

    op.bulk_insert(
        contracts,
        [
            {
                "id": "contract-001",
                "company_id": "company-hantos",
                "name": "Договор на геологические исследования",
                "is_active": True,
                "product_ids": ["product-reserves", "product-geology"],
            },
            {
                "id": "contract-002",
                "company_id": "company-megion",
                "name": "Договор на оценку запасов",
                "is_active": True,
                "product_ids": ["product-reserves"],
            },
            {
                "id": "contract-003",
                "company_id": "company-angara",
                "name": "Договор на стратегические концепты",
                "is_active": True,
                "product_ids": ["product-concept", "product-development"],
            },
        ],
    )

    historical_cases = sa.table(
        "historical_cases",
        sa.column("id", sa.String()),
        sa.column("product_id", sa.String()),
        sa.column("company_id", sa.String()),
        sa.column("title", sa.String()),
        sa.column("summary", sa.Text()),
        sa.column("object_name", sa.String()),
    )

    op.bulk_insert(
        historical_cases,
        [
            {
                "id": "case-001",
                "product_id": "product-reserves",
                "company_id": "company-hantos",
                "title": "Подсчёт запасов по Северному блоку",
                "summary": "Выполнена оценка запасов с полным циклом подготовки отчёта.",
                "object_name": "Северный блок",
            },
            {
                "id": "case-002",
                "product_id": "product-concept",
                "company_id": "company-angara",
                "title": "Концепт обустройства для месторождения Вега",
                "summary": "Подготовлено 3 варианта инфраструктурного обустройства.",
                "object_name": "Месторождение Вега",
            },
            {
                "id": "case-003",
                "product_id": "product-development",
                "company_id": "company-angara",
                "title": "Интегрированный концепт развития актива Восток",
                "summary": "Собраны сценарии развития и сравнительная экономика.",
                "object_name": "Актив Восток",
            },
        ],
    )

    intents = sa.table(
        "intent_prompts",
        sa.column("intent", sa.String()),
        sa.column("prompt", sa.Text()),
    )

    op.bulk_insert(
        intents,
        [
            {
                "intent": "service_search",
                "prompt": "Пользователь хочет найти услугу или подобрать продукт для работы.",
            },
            {
                "intent": "contractor_selection",
                "prompt": "Пользователь хочет выбрать исполнителя, подрядчика или компанию.",
            },
            {
                "intent": "similar_cases",
                "prompt": "Пользователь просит показать похожие ранее выполненные работы или аналоги.",
            },
            {
                "intent": "draft_generation",
                "prompt": "Пользователь просит сформировать техническое задание или черновик заявки.",
            },
        ],
    )
