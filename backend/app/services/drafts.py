from uuid import uuid4

from backend.app.models.domain import RequestDraft
from backend.app.schemas.draft import DraftFromSearchRequest
from backend.app.services.catalog import catalog_service
from backend.app.services.rules import rules_service


class DraftService:
    def create_from_search(self, payload: DraftFromSearchRequest) -> RequestDraft:
        product = catalog_service.get_product(payload.product_id)
        template = catalog_service.get_template_by_product(payload.product_id)
        companies = catalog_service.list_product_companies(payload.product_id)
        company = catalog_service.get_company(payload.company_id) if payload.company_id else (companies[0] if companies else None)
        contracts = catalog_service.list_product_contracts(payload.product_id, company.id if company else None)
        contract = catalog_service.get_contract(payload.contract_id) if payload.contract_id else (contracts[0] if contracts else None)

        required_fields = [
            field
            for section in template.sections
            for field in section.required_fields
        ]

        draft = RequestDraft(
            id=f"draft-{uuid4().hex[:8]}",
            product_id=product.id,
            product_name=product.name,
            template_id=template.id,
            company_id=company.id if company else None,
            company_name=company.name if company else None,
            contract_id=contract.id if contract else None,
            contract_name=contract.name if contract else None,
            stages=template.stage_presets,
            required_fields=required_fields,
            input_data=payload.input_data,
            notes=[f"Черновик создан из поиска по запросу: {payload.query or 'без текста запроса'}."],
        )
        return rules_service.evaluate(draft)


draft_service = DraftService()

