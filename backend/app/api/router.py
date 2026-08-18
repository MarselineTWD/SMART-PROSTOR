from fastapi import APIRouter

from backend.app.api.routes.analytics import router as analytics_router
from backend.app.api.routes.assistant import router as assistant_router
from backend.app.api.routes.drafts import router as drafts_router
from backend.app.api.routes.estimates import router as estimates_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.normative_acts import router as normative_acts_router
from backend.app.api.routes.search import router as search_router
from backend.app.api.routes.tz import router as tz_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(drafts_router, prefix="/drafts", tags=["drafts"])
api_router.include_router(tz_router, prefix="/tz", tags=["tz"])
api_router.include_router(estimates_router, prefix="/estimates", tags=["estimates"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
api_router.include_router(assistant_router, prefix="/assistant", tags=["assistant"])
api_router.include_router(normative_acts_router, prefix="/normative-acts", tags=["normative-acts"])
