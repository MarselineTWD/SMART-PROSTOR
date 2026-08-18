"""In-memory catalog with a Postgres snapshot as source of truth.

Public API is intentionally unchanged from the previous mocks-backed
version: sync methods returning Pydantic domain models. The only
difference is that the data now comes from Postgres — refreshed once
on app startup via `refresh(session)` and served from an in-memory
dict thereafter.

Templates remain hardcoded in `backend.app.data.catalog.TEMPLATES`:
the domain templates power the legacy drafts/rules pipeline and their
schema is not (yet) modelled in Postgres.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.data.catalog import TEMPLATES
from backend.app.models.domain import (
    Company,
    Contract,
    HistoricalCase,
    Product,
    Template,
)
from backend.app.services.db_catalog import CatalogSnapshot, load_snapshot


class CatalogService:
    def __init__(self) -> None:
        self._companies: dict[str, Company] = {}
        self._contracts: dict[str, Contract] = {}
        self._products: dict[str, Product] = {}
        self._templates: dict[str, Template] = {tpl.id: tpl for tpl in TEMPLATES}
        self._historical_cases: list[HistoricalCase] = []
        self._loaded: bool = False

    # -- lifecycle -----------------------------------------------------------

    async def refresh(self, session: AsyncSession) -> None:
        """Replace the in-memory snapshot with a fresh Postgres dump."""
        snapshot = await load_snapshot(session, seed_templates=TEMPLATES)
        self._replace(snapshot)

    def _replace(self, snapshot: CatalogSnapshot) -> None:
        self._companies = {c.id: c for c in snapshot.companies}
        self._contracts = {c.id: c for c in snapshot.contracts}
        self._products = {p.id: p for p in snapshot.products}
        # Templates from snapshot may include DB-backed ones later;
        # for now `seed_templates=TEMPLATES` keeps behavior identical.
        self._templates = {t.id: t for t in snapshot.templates}
        self._historical_cases = list(snapshot.historical_cases)
        self._loaded = True

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # -- reads ---------------------------------------------------------------

    def list_products(self) -> list[Product]:
        return list(self._products.values())

    def get_product(self, product_id: str) -> Product:
        return self._products[product_id]

    def list_companies(self) -> list[Company]:
        return list(self._companies.values())

    def get_company(self, company_id: str) -> Company:
        return self._companies[company_id]

    def list_contracts(self) -> list[Contract]:
        return list(self._contracts.values())

    def get_contract(self, contract_id: str) -> Contract:
        return self._contracts[contract_id]

    def get_template_by_product(self, product_id: str) -> Template:
        for template in self._templates.values():
            if template.product_id == product_id:
                return template
        raise KeyError(product_id)

    def list_product_companies(self, product_id: str) -> list[Company]:
        companies = [
            company for company in self._companies.values() if product_id in company.product_ids
        ]
        return sorted(companies, key=lambda item: item.rating, reverse=True)

    def list_product_contracts(
        self, product_id: str, company_id: str | None = None
    ) -> list[Contract]:
        contracts = [
            contract
            for contract in self._contracts.values()
            if product_id in contract.product_ids
        ]
        if company_id:
            contracts = [c for c in contracts if c.company_id == company_id]
        return contracts

    def list_historical_cases(self, product_id: str) -> list[HistoricalCase]:
        return [item for item in self._historical_cases if item.product_id == product_id]


catalog_service = CatalogService()
