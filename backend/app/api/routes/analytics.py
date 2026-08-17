from fastapi import APIRouter

from backend.app.schemas.analytics import AnalyticsOverview
from backend.app.services.analytics import analytics_service


router = APIRouter()


@router.get("/overview", response_model=AnalyticsOverview)
def overview() -> AnalyticsOverview:
    return analytics_service.overview()

