"""Load domain-shaped catalog snapshots from PostgreSQL.

The rest of the app (`rules`, `drafts`, `analytics`, legacy `search`)
consumes Pydantic domain models via a sync `CatalogService`. This
module provides an async loader that populates those models from the
DB in one shot; the sync accessors then serve the in-memory snapshot.

Why a snapshot instead of async DB calls everywhere:
* zero refactor of downstream services;
* datasets fit trivially in memory (~60 products, 13 companies,
  ~500 contracts, ~462 historical cases — under 2 MB);
* refresh is cheap and can be called from an admin endpoint later.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import db as orm
from backend.app.models.domain import (
    Company,
    Contract,
    HistoricalCase,
    Product,
    Template,
)


@dataclass
class CatalogSnapshot:
    products: list[Product] = field(default_factory=list)
    companies: list[Company] = field(default_factory=list)
    contracts: list[Contract] = field(default_factory=list)
    historical_cases: list[HistoricalCase] = field(default_factory=list)
    templates: list[Template] = field(default_factory=list)


async def load_snapshot(session: AsyncSession, seed_templates: Sequence[Template]) -> CatalogSnapshot:
    """Read the whole catalog from Postgres and return domain models."""
    # ---- raw fetches --------------------------------------------------------
    products_orm = (await session.execute(select(orm.Product))).scalars().all()
    companies_orm = (await session.execute(select(orm.Company))).scalars().all()
    contracts_orm = (await session.execute(select(orm.Contract))).scalars().all()
    cases_orm = (await session.execute(select(orm.HistoricalCase))).scalars().all()

    # Cross-links: contracts.product_ids (ARRAY on seeded rows) + xlsx-derived
    # rows in pr_contract_products (row-per-link on xlsx rows).
    pr_links_orm = (
        await session.execute(select(orm.ProcurementContractProductORM))
    ).scalars().all()

    # ---- derive company -> products, product -> contracts, company -> contracts
    company_to_products: dict[str, set[str]] = defaultdict(set)
    product_to_contracts: dict[str, set[str]] = defaultdict(set)

    for contract in contracts_orm:
        for pid in contract.product_ids or []:
            company_to_products[contract.company_id].add(pid)
            product_to_contracts[pid].add(contract.id)

    for link in pr_links_orm:
        company_to_products[link.company_id].add(link.product_id)
        if link.contract_id:
            product_to_contracts[link.product_id].add(link.contract_id)

    # ---- domain models ------------------------------------------------------
    products = [
        Product(
            id=p.id,
            name=p.name,
            summary=p.summary or "",
            keywords=list(p.keywords or []),
            operations=list(p.operations or []),
            active_contract_ids=sorted(product_to_contracts.get(p.id, set())),
            template_id=p.template_id or "",
            has_price_rules=bool(p.has_price_rules),
            has_operations=bool(p.has_operations),
            is_legacy=bool(p.is_legacy),
            synonyms=list(p.synonyms or []),
        )
        for p in products_orm
    ]

    companies = [
        Company(
            id=c.id,
            name=c.name,
            description=c.description or "",
            rating=float(c.rating or 0.0),
            product_ids=sorted(company_to_products.get(c.id, set())),
            subcontract_policy=(c.subcontract_policy or "allowed"),  # type: ignore[arg-type]
        )
        for c in companies_orm
    ]

    contracts = [
        Contract(
            id=c.id,
            company_id=c.company_id,
            name=c.name,
            is_active=bool(c.is_active),
            product_ids=list(c.product_ids or []),
        )
        for c in contracts_orm
    ]

    cases = [
        HistoricalCase(
            id=h.id,
            product_id=h.product_id,
            title=h.title or "",
            summary=h.summary or "",
            company_id=h.company_id or "",
            object_name=h.object_name or "",
        )
        for h in cases_orm
    ]

    return CatalogSnapshot(
        products=products,
        companies=companies,
        contracts=contracts,
        historical_cases=cases,
        templates=list(seed_templates),
    )
