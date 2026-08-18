from pydantic import BaseModel, Field

from backend.app.models.domain import IntentType, SearchContext


class SearchRequest(BaseModel):
    query: str = Field(min_length=3)
    limit: int = Field(default=3, ge=1, le=5)


class SearchResponse(BaseModel):
    query: str
    detected_intent: IntentType
    results: SearchContext


class SimilarCasesRequest(BaseModel):
    query: str = Field(min_length=3)
    limit: int = Field(default=5, ge=1, le=20)
    min_similarity: float = Field(default=0.30, ge=0.0, le=1.0)


class SimilarCaseItem(BaseModel):
    id: str
    title: str
    summary: str
    object_name: str
    product_id: str
    product_name: str | None
    company_id: str | None
    company_name: str | None
    similarity: float


class SimilarCasesResponse(BaseModel):
    query: str
    results: list[SimilarCaseItem]

