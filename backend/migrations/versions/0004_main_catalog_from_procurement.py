"""main catalog + historical cases from procurement_seed

Revision ID: 0004_main_catalog
Revises: 0003_procurement
Create Date: 2026-08-18 00:00:00

Расширяет главные таблицы (`companies`, `products`, `historical_cases`)
данными из ``backend/app/data/procurement_seed.json``, чтобы:

* фронт видел реальный каталог (13 подрядчиков и ~60 продуктов ПРОСТОР),
  а не 3 демо-компании из 0001;
* работал pgvector-поиск по 462 историческим заказам — из calcs+stages
  собираются осмысленные summary-тексты, `embedding` остаётся NULL и
  наполняется скриптом ``backend.app.scripts.embed_seeds`` на старте.

Идемпотентно: пропускает строки, чей PK уже есть в целевой таблице.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0004_main_catalog"
down_revision: Union[str, None] = "0003_procurement"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEED_PATH = (
    Path(__file__).resolve().parents[2] / "app" / "data" / "procurement_seed.json"
)

CHUNK_SIZE = 500


def _chunked(rows: Sequence[dict], size: int = CHUNK_SIZE) -> Iterable[list[dict]]:
    for i in range(0, len(rows), size):
        yield list(rows[i : i + size])


def _existing_ids(table: str, column: str) -> set:
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"SELECT {column} FROM {table}")).fetchall()
    return {r[0] for r in rows}


def _bulk_append(table, rows: list[dict]) -> None:
    for chunk in _chunked(rows):
        if chunk:
            op.bulk_insert(table, chunk)


def _clean(text: Any) -> str:
    if text is None:
        return ""
    return str(text).strip()


def upgrade() -> None:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))

    # ---- companies ----------------------------------------------------------
    companies_tbl = sa.table(
        "companies",
        sa.column("id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("rating", sa.Float()),
        sa.column("subcontract_policy", sa.String()),
    )
    existing_company_ids = _existing_ids("companies", "id")
    company_rows = []
    for c in seed["companies"]:
        if c["id"] in existing_company_ids:
            continue
        parts = [_clean(c.get("info")), _clean(c.get("services"))]
        company_rows.append(
            {
                "id": c["id"],
                "name": _clean(c.get("name")),
                "description": "\n\n".join(p for p in parts if p),
                "rating": float(c.get("rating") or 0.0),
                "subcontract_policy": "allowed",
            }
        )
    _bulk_append(companies_tbl, company_rows)

    # ---- products -----------------------------------------------------------
    # Соберём набор операций по каждому продукту — попадёт в колонку
    # `operations` и заметно улучшит качество эмбеддинга.
    ops_by_product: dict[str, list[str]] = defaultdict(list)
    for op_row in seed.get("operations", []):
        pid = op_row.get("product_id")
        name = _clean(op_row.get("operation_name"))
        if pid and name:
            ops_by_product[pid].append(name)

    priced_pids = {p["product_id"] for p in seed.get("prices", []) if p.get("product_id")}
    op_pids = set(ops_by_product.keys())

    products_tbl = sa.table(
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
    existing_product_ids = _existing_ids("products", "id")
    product_rows = []
    for p in seed["products"]:
        pid = p["id"]
        if pid in existing_product_ids:
            continue
        name = _clean(p.get("name"))
        ops = ops_by_product.get(pid, [])
        summary_bits: list[str] = []
        if ops:
            summary_bits.append("Типичные операции: " + "; ".join(ops[:6]))
        product_rows.append(
            {
                "id": pid,
                "name": name,
                "summary": " ".join(summary_bits),
                "keywords": [],
                "operations": ops[:20],
                "synonyms": [],
                "template_id": None,
                "has_price_rules": pid in priced_pids,
                "has_operations": pid in op_pids,
                "is_legacy": name.upper().startswith("НЕАКТУАЛЬНО"),
            }
        )
    _bulk_append(products_tbl, product_rows)

    # ---- historical_cases ---------------------------------------------------
    # Один case на calc_id; текст собирается из calc.name + первых 8 этапов
    # + уникальных документов. Именно это уходит в эмбеддинг и питает
    # семантический поиск похожих работ.
    stages_by_calc: dict[str, list[dict]] = defaultdict(list)
    for st in seed.get("stages", []):
        cid = st.get("calc_id")
        if cid:
            stages_by_calc[cid].append(st)

    company_names = {c["id"]: _clean(c.get("name")) for c in seed["companies"]}
    known_products_after = existing_product_ids | {p["id"] for p in seed["products"]}
    known_companies_after = existing_company_ids | set(company_names.keys())

    historical_cases_tbl = sa.table(
        "historical_cases",
        sa.column("id", sa.String()),
        sa.column("product_id", sa.String()),
        sa.column("company_id", sa.String()),
        sa.column("title", sa.String()),
        sa.column("summary", sa.Text()),
        sa.column("object_name", sa.String()),
    )
    existing_case_ids = _existing_ids("historical_cases", "id")

    case_rows = []
    for calc in seed.get("calcs", []):
        case_id = f"case-{calc['calc_id']}"
        if case_id in existing_case_ids:
            continue
        product_id = calc.get("product_id")
        if product_id not in known_products_after:
            continue
        company_id = calc.get("company_id")
        if company_id not in known_companies_after:
            company_id = None

        stages = sorted(
            stages_by_calc.get(calc["calc_id"], []),
            key=lambda s: s.get("order_num") or 0,
        )
        stage_names = [_clean(s.get("name")) for s in stages if _clean(s.get("name"))][:8]
        docs: list[str] = []
        seen_docs: set[str] = set()
        for s in stages:
            doc = _clean(s.get("documentation"))
            if doc and doc not in seen_docs:
                seen_docs.add(doc)
                docs.append(doc)

        product_name = _clean(calc.get("product_name"))
        summary_parts = [_clean(calc.get("name"))]
        if product_name:
            summary_parts.append(f"Продукт: {product_name}")
        if stage_names:
            summary_parts.append("Ключевые этапы: " + "; ".join(stage_names))
        if docs:
            summary_parts.append("Документация: " + "; ".join(docs[:4]))
        if company_id and company_id in company_names:
            summary_parts.append(f"Исполнитель: {company_names[company_id]}")
        summary = ". ".join(p for p in summary_parts if p)

        title = (_clean(calc.get("name")) or product_name)[:200]

        case_rows.append(
            {
                "id": case_id,
                "product_id": product_id,
                "company_id": company_id,
                "title": title,
                "summary": summary,
                "object_name": product_name,
            }
        )
    _bulk_append(historical_cases_tbl, case_rows)


def downgrade() -> None:
    bind = op.get_bind()
    # Historical cases derived here have PK prefix 'case-' + hash != 'case-001..003'.
    seed_hashes = set()
    try:
        seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        seed_hashes = {f"case-{c['calc_id']}" for c in seed.get("calcs", [])}
    except FileNotFoundError:
        pass
    if seed_hashes:
        bind.execute(
            sa.text("DELETE FROM historical_cases WHERE id = ANY(:ids)"),
            {"ids": list(seed_hashes)},
        )
    # Best-effort: drop xlsx-imported products/companies (hash IDs) that
    # are no longer referenced by any historical case.
    bind.execute(
        sa.text(
            "DELETE FROM products WHERE id NOT LIKE 'product-%' "
            "AND id NOT IN (SELECT product_id FROM historical_cases)"
        )
    )
    bind.execute(sa.text("DELETE FROM companies WHERE id NOT LIKE 'company-%'"))
