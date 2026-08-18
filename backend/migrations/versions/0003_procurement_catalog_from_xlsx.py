"""procurement catalog imported from xlsx exports

Revision ID: 0003_procurement
Revises: 0002_tz
Create Date: 2026-08-17 13:00:00

Переносит справочные данные ПРОСТОР из xlsx-выгрузок в БД: компании, договоры,
продукты, связки договор+продукт, расценки, операции, расчёты стоимости (РС) и
этапы РС. Источник — committed-файл backend/app/data/procurement_seed.json
(сгенерирован из xlsx один раз), поэтому во время выполнения приложение не
зависит от xlsx.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_procurement"
down_revision: Union[str, None] = "0002_tz"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_PATH = Path(__file__).resolve().parents[3] / "backend" / "app" / "data" / "procurement_seed.json"

TABLES = (
    "pr_stages", "pr_calcs", "pr_operations", "pr_prices",
    "pr_contract_products", "pr_products", "pr_contracts", "pr_companies",
)
INDEXES = (
    ("ix_pr_calcs_product", "pr_calcs", ["product_id"]),
    ("ix_pr_calcs_company", "pr_calcs", ["company_id"]),
    ("ix_pr_stages_calc", "pr_stages", ["calc_id"]),
    ("ix_pr_operations_product", "pr_operations", ["product_id"]),
    ("ix_pr_prices_product", "pr_prices", ["product_id"]),
)


def _d(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def upgrade() -> None:
    op.create_table(
        "pr_companies",
        sa.Column("company_id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("info", sa.Text(), nullable=False, server_default=""),
        sa.Column("services", sa.Text(), nullable=False, server_default=""),
        sa.Column("rating", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_table(
        "pr_contracts",
        sa.Column("contract_id", sa.String(), primary_key=True),
        sa.Column("number", sa.String(), nullable=False, server_default=""),
        sa.Column("company_id", sa.String(), nullable=False),
    )
    op.create_table(
        "pr_products",
        sa.Column("product_id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, server_default=""),
    )
    op.create_table(
        "pr_contract_products",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.String(), nullable=False),
        sa.Column("contract_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
    )
    op.create_table(
        "pr_prices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("price_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("price_name", sa.String(), nullable=False, server_default=""),
        sa.Column("measurement_name", sa.String(), nullable=False, server_default=""),
        sa.Column("measurement_type", sa.String(), nullable=False, server_default=""),
    )
    op.create_table(
        "pr_operations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("operation_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("operation_name", sa.Text(), nullable=False, server_default=""),
    )
    op.create_table(
        "pr_calcs",
        sa.Column("calc_id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), nullable=False),
        sa.Column("contract_id", sa.String(), nullable=True),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("product_name", sa.String(), nullable=False, server_default=""),
        sa.Column("name", sa.Text(), nullable=False, server_default=""),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
    )
    op.create_table(
        "pr_stages",
        sa.Column("stage_id", sa.String(), primary_key=True),
        sa.Column("calc_id", sa.String(), nullable=False),
        sa.Column("parent_stage_id", sa.String(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False, server_default=""),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("order_num", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("documentation", sa.Text(), nullable=False, server_default=""),
    )
    for name, table, cols in INDEXES:
        op.create_index(name, table, cols)
    _seed()


def downgrade() -> None:
    for name, _table, _cols in INDEXES:
        op.drop_index(name)
    for table in TABLES:
        op.drop_table(table)


def _seed() -> None:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))

    op.bulk_insert(sa.table(
        "pr_companies",
        sa.column("company_id", sa.String()), sa.column("name", sa.String()),
        sa.column("info", sa.Text()), sa.column("services", sa.Text()),
        sa.column("rating", sa.Float()),
    ), [{"company_id": r["id"], "name": r["name"], "info": r["info"],
         "services": r["services"], "rating": r["rating"]} for r in seed["companies"]])

    op.bulk_insert(sa.table(
        "pr_contracts",
        sa.column("contract_id", sa.String()), sa.column("number", sa.String()),
        sa.column("company_id", sa.String()),
    ), [{"contract_id": r["id"], "number": r["number"], "company_id": r["company_id"]}
        for r in seed["contracts"]])

    op.bulk_insert(sa.table(
        "pr_products", sa.column("product_id", sa.String()), sa.column("name", sa.String()),
    ), [{"product_id": r["id"], "name": r["name"]} for r in seed["products"]])

    op.bulk_insert(sa.table(
        "pr_contract_products",
        sa.column("company_id", sa.String()), sa.column("contract_id", sa.String()),
        sa.column("product_id", sa.String()),
    ), [{"company_id": r["company_id"], "contract_id": r["contract_id"],
         "product_id": r["product_id"]} for r in seed["contract_products"]])

    op.bulk_insert(sa.table(
        "pr_prices",
        sa.column("price_id", sa.String()), sa.column("product_id", sa.String()),
        sa.column("price_name", sa.String()), sa.column("measurement_name", sa.String()),
        sa.column("measurement_type", sa.String()),
    ), [{"price_id": r["price_id"], "product_id": r["product_id"], "price_name": r["price_name"],
         "measurement_name": r["measurement_name"], "measurement_type": r["measurement_type"]}
        for r in seed["prices"]])

    op.bulk_insert(sa.table(
        "pr_operations",
        sa.column("operation_id", sa.String()), sa.column("product_id", sa.String()),
        sa.column("operation_name", sa.Text()),
    ), [{"operation_id": r["operation_id"], "product_id": r["product_id"],
         "operation_name": r["operation_name"]} for r in seed["operations"]])

    op.bulk_insert(sa.table(
        "pr_calcs",
        sa.column("calc_id", sa.String()), sa.column("company_id", sa.String()),
        sa.column("contract_id", sa.String()), sa.column("product_id", sa.String()),
        sa.column("product_name", sa.String()), sa.column("name", sa.Text()),
        sa.column("start_date", sa.Date()), sa.column("end_date", sa.Date()),
    ), [{"calc_id": r["calc_id"], "company_id": r["company_id"], "contract_id": r["contract_id"],
         "product_id": r["product_id"], "product_name": r["product_name"], "name": r["name"],
         "start_date": _d(r["start_date"]), "end_date": _d(r["end_date"])}
        for r in seed["calcs"]])

    op.bulk_insert(sa.table(
        "pr_stages",
        sa.column("stage_id", sa.String()), sa.column("calc_id", sa.String()),
        sa.column("parent_stage_id", sa.String()), sa.column("name", sa.Text()),
        sa.column("start_date", sa.Date()), sa.column("end_date", sa.Date()),
        sa.column("order_num", sa.Integer()), sa.column("documentation", sa.Text()),
    ), [{"stage_id": r["stage_id"], "calc_id": r["calc_id"], "parent_stage_id": r["parent_stage_id"],
         "name": r["name"], "start_date": _d(r["start_date"]), "end_date": _d(r["end_date"]),
         "order_num": r["order_num"], "documentation": r["documentation"]}
        for r in seed["stages"]])
