from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.db import get_session
from backend.app.schemas.normative_acts import (
    NormativeActItem,
    NormativeActsResponse,
    SimilarActItem,
    SimilarActsRequest,
    SimilarActsResponse,
)
from backend.app.services.normative_acts import normative_act_service


router = APIRouter()


def _to_item(act) -> NormativeActItem:
    return NormativeActItem(
        id=act.id,
        document_type=act.document_type,
        authority=act.authority,
        number=act.number,
        date_issued=act.date_issued,
        title=act.title,
        short_title=act.short_title,
        url=act.url,
        is_active=act.is_active,
    )


@router.get("", response_model=NormativeActsResponse)
def list_acts(template_key: str | None = None) -> NormativeActsResponse:
    """Список нормативно-правовых актов.

    Если задан `template_key` — возвращаются акты, регламентирующие
    порядок выполнения работ по этому типу ТЗ (в порядке из шаблона).
    Без параметра — весь справочник.
    """
    if template_key:
        acts = normative_act_service.acts_for_template(template_key)
    else:
        acts = normative_act_service.all_acts()
    return NormativeActsResponse(
        template_key=template_key,
        total=len(acts),
        acts=[_to_item(a) for a in acts],
    )


@router.post("/similar", response_model=SimilarActsResponse)
async def similar_acts(
    payload: SimilarActsRequest,
    session: AsyncSession = Depends(get_session),
) -> SimilarActsResponse:
    """Семантический подбор релевантных НПА по описанию работ (pgvector)."""
    hits = await normative_act_service.similar_acts(
        session=session,
        query=payload.query,
        limit=payload.limit,
        min_similarity=payload.min_similarity,
    )
    return SimilarActsResponse(
        query=payload.query,
        results=[
            SimilarActItem(**_to_item(act).model_dump(), similarity=sim)
            for act, sim in hits
        ],
    )
