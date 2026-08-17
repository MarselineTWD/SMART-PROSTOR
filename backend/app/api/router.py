from fastapi import APIRouter

from backend.app.api.routes.analytics import router as analytics_router
from backend.app.api.routes.assistant import router as assistant_router
from backend.app.api.routes.drafts import router as drafts_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.search import router as search_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(drafts_router, prefix="/drafts", tags=["drafts"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
api_router.include_router(assistant_router, prefix="/assistant", tags=["assistant"])
