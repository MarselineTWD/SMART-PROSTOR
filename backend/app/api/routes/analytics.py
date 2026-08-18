from fastapi import APIRouter, HTTPException

from backend.app.schemas.analytics import AnalyticsOverview
from backend.app.schemas.contractor_analytics import (
    ContractorLeaderboardResponse,
    ContractorProductMatrixResponse,
    ContractorProfileResponse,
    ContractorWorkloadResponse,
)
from backend.app.services.analytics import analytics_service
from backend.app.services.procurement import procurement_service


router = APIRouter()


@router.get("/overview", response_model=AnalyticsOverview)
def overview() -> AnalyticsOverview:
    return analytics_service.overview()


# ---- Аналитика по подрядчикам -----------------------------------------------


@router.get("/contractors", response_model=ContractorLeaderboardResponse)
def contractors_leaderboard() -> ContractorLeaderboardResponse:
    """Сводка по всем подрядчикам: топ-борды и доля рынка."""
    data = procurement_service.contractor_leaderboard()
    return ContractorLeaderboardResponse(**data)


@router.get(
    "/contractors/matrix",
    response_model=ContractorProductMatrixResponse,
)
def contractors_product_matrix() -> ContractorProductMatrixResponse:
    """Матрица «подрядчик × продукт» + покрытие каждого продукта."""
    data = procurement_service.contractor_product_matrix()
    return ContractorProductMatrixResponse(**data)


@router.get(
    "/contractors/{company_id}",
    response_model=ContractorProfileResponse,
)
def contractor_profile(company_id: str) -> ContractorProfileResponse:
    """Профиль подрядчика: продуктовая линейка, договоры, средние показатели."""
    data = procurement_service.contractor_profile(company_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Подрядчик не найден")
    return ContractorProfileResponse(**data)


@router.get(
    "/contractors/{company_id}/workload",
    response_model=ContractorWorkloadResponse,
)
def contractor_workload(company_id: str) -> ContractorWorkloadResponse:
    """Помесячная загрузка подрядчика — для UI-графика загрузки."""
    data = procurement_service.contractor_workload(company_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Подрядчик не найден")
    return ContractorWorkloadResponse(**data)

