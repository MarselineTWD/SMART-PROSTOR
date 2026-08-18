import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import api_router
from backend.app.core.config import settings
from backend.app.core.db import SessionLocal
from backend.app.services.catalog import catalog_service
from backend.app.services.normative_acts import normative_act_service
from backend.app.scripts.upload_templates import sync_templates_to_minio


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Snapshot the DB catalog into memory at startup. Downstream services
    # (rules/drafts/analytics/search) then read from the sync `catalog_service`.
    try:
        async with SessionLocal() as session:
            await catalog_service.refresh(session)
            await normative_act_service.refresh(session)
        logger.info(
            "catalog snapshot loaded: products=%d companies=%d contracts=%d cases=%d acts=%d",
            len(catalog_service.list_products()),
            len(catalog_service.list_companies()),
            len(catalog_service.list_contracts()),
            sum(1 for p in catalog_service.list_products()
                for _ in catalog_service.list_historical_cases(p.id)),
            len(normative_act_service.all_acts()),
        )
    except Exception:
        # DB not reachable on startup is not fatal — routes hitting the
        # catalog will surface a 500 with a clear log, which is preferable
        # to preventing the app from booting at all.
        logger.exception("catalog snapshot failed; serving empty catalog")

    # Одноразовая заливка docx-шаблонов в MinIO. Синхронный boto3 в
    # executor — не блокирует старт даже если бакет холодный.
    try:
        loop = asyncio.get_running_loop()
        uploaded = await loop.run_in_executor(None, sync_templates_to_minio)
        if uploaded:
            logger.info("templates synced to MinIO: %d files", uploaded)
    except Exception:
        logger.exception("templates sync to MinIO failed")

    yield


def create_app() -> FastAPI:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "MVP backend for PROSTOR: product search, RequestDraft generation, "
            "and rules-based readiness scoring."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
