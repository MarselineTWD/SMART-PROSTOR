from pydantic import BaseModel, Field

from backend.app.models.domain import IntentType, SearchContext


class SearchRequest(BaseModel):
    query: str = Field(min_length=3)
    limit: int = Field(default=3, ge=1, le=5)


class SearchResponse(BaseModel):
    query: str
    detected_intent: IntentType
    results: SearchContext

