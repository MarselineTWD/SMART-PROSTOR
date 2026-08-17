from fastapi import APIRouter

from backend.app.schemas.search import SearchRequest, SearchResponse
from backend.app.services.search import search_service


router = APIRouter()


@router.post("/query", response_model=SearchResponse)
def search(payload: SearchRequest) -> SearchResponse:
    results = search_service.search(payload.query, payload.limit)
    return SearchResponse(
        query=payload.query,
        detected_intent=results.detected_intent,
        results=results,
    )

