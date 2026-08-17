from backend.app.data.catalog import COMPANIES, CONTRACTS, HISTORICAL_CASES, PRODUCTS, TEMPLATES
from backend.app.models.domain import Company, Contract, HistoricalCase, Product, Template


class CatalogService:
    def __init__(self) -> None:
        self._companies = {item.id: item for item in COMPANIES}
        self._contracts = {item.id: item for item in CONTRACTS}
        self._products = {item.id: item for item in PRODUCTS}
        self._templates = {item.id: item for item in TEMPLATES}
        self._historical_cases = HISTORICAL_CASES

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

    def list_product_contracts(self, product_id: str, company_id: str | None = None) -> list[Contract]:
        contracts = [contract for contract in self._contracts.values() if product_id in contract.product_ids]
        if company_id:
            contracts = [contract for contract in contracts if contract.company_id == company_id]
        return contracts

    def list_historical_cases(self, product_id: str) -> list[HistoricalCase]:
        return [item for item in self._historical_cases if item.product_id == product_id]


catalog_service = CatalogService()

