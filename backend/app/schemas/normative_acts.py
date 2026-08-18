from datetime import date

from pydantic import BaseModel, Field


class NormativeActItem(BaseModel):
    id: str
    document_type: str
    authority: str | None
    number: str | None
    date_issued: date | None
    title: str
    short_title: str
    url: str | None
    is_active: bool


class NormativeActsResponse(BaseModel):
    template_key: str | None
    total: int
    acts: list[NormativeActItem]


class SimilarActItem(NormativeActItem):
    similarity: float


class SimilarActsRequest(BaseModel):
    query: str = Field(min_length=3)
    limit: int = Field(default=5, ge=1, le=20)
    min_similarity: float = Field(default=0.35, ge=0.0, le=1.0)


class SimilarActsResponse(BaseModel):
    query: str
    results: list[SimilarActItem]
