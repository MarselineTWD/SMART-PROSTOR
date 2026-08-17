from pydantic import BaseModel, Field

from backend.app.models.domain import DraftInputData, RequestDraft


class DraftFromSearchRequest(BaseModel):
    product_id: str
    company_id: str | None = None
    contract_id: str | None = None
    query: str | None = None
    input_data: DraftInputData = Field(default_factory=DraftInputData)


class DraftEvaluationRequest(BaseModel):
    draft: RequestDraft


class DraftResponse(BaseModel):
    draft: RequestDraft

