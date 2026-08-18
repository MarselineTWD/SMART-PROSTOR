from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.db import get_session
from backend.app.schemas.search import (
    SearchRequest,
    SearchResponse,
    SimilarCaseItem,
    SimilarCasesRequest,
    SimilarCasesResponse,
)
from backend.app.services.historical_search import historical_search_service
from backend.app.services.search import search_service


router = APIRouter()


@router.post("/query", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    results = await search_service.search(
        session=session,
        query=payload.query,
        limit=payload.limit,
    )
    return SearchResponse(
        query=payload.query,
        detected_intent=results.detected_intent,
        results=results,
    )


@router.post("/similar-cases", response_model=SimilarCasesResponse)
async def similar_cases(
    payload: SimilarCasesRequest,
    session: AsyncSession = Depends(get_session),
) -> SimilarCasesResponse:
    """Семантический поиск похожих исторических заказов через pgvector."""
    hits = await historical_search_service.similar_cases(
        session=session,
        query=payload.query,
        limit=payload.limit,
        min_similarity=payload.min_similarity,
    )
    return SimilarCasesResponse(
        query=payload.query,
        results=[SimilarCaseItem(**hit.__dict__) for hit in hits],
    )
