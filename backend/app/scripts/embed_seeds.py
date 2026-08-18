"""Compute embeddings for rows where `embedding IS NULL`.

Runs after Alembic migration. Idempotent: safe to invoke on every start,
only backfills what is missing.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from backend.app.core.db import SessionLocal
from backend.app.models.db import Company, HistoricalCase, IntentPrompt, Product
from backend.app.services.embeddings import get_embeddings_service


logger = logging.getLogger(__name__)


async def _has_missing_embeddings(session) -> bool:
    """Avoid loading the ML model when the database is already backfilled."""
    for entity_cls in (Product, Company, HistoricalCase, IntentPrompt):
        result = await session.execute(
            select(entity_cls.id).where(entity_cls.embedding.is_(None)).limit(1)
        )
        if result.scalar_one_or_none() is not None:
            return True
    return False


def _product_text(p: Product) -> str:
    parts = [p.name, p.summary]
    if p.keywords:
        parts.append("Ключевые термины: " + ", ".join(p.keywords))
    if p.operations:
        parts.append("Операции: " + ", ".join(p.operations))
    if p.synonyms:
        parts.append("Синонимы: " + ", ".join(p.synonyms))
    return "\n".join(parts)


def _company_text(c: Company) -> str:
    return f"{c.name}. {c.description}"


def _case_text(h: HistoricalCase) -> str:
    return f"{h.title}. Объект: {h.object_name}. {h.summary}"


async def _embed_missing(session, model, entity_cls, text_fn) -> int:
    result = await session.execute(select(entity_cls).where(entity_cls.embedding.is_(None)))
    rows = list(result.scalars())
    if not rows:
        return 0

    texts = [text_fn(row) for row in rows]
    vectors = model.embed_passages(texts)
    for row, vec in zip(rows, vectors):
        row.embedding = vec
    await session.commit()
    return len(rows)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")

    async with SessionLocal() as session:
        if not await _has_missing_embeddings(session):
            logger.info("Embeddings are up to date; model loading skipped.")
            return

    logger.info("Loading embedding model...")
    model = get_embeddings_service()
    logger.info("Model ready.")

    async with SessionLocal() as session:
        n_products = await _embed_missing(session, model, Product, _product_text)
        n_companies = await _embed_missing(session, model, Company, _company_text)
        n_cases = await _embed_missing(session, model, HistoricalCase, _case_text)

        # Intent prompts are stored as-is (already look like `query:` style).
        result = await session.execute(
            select(IntentPrompt).where(IntentPrompt.embedding.is_(None))
        )
        intents = list(result.scalars())
        if intents:
            vectors = model.embed_passages([i.prompt for i in intents])
            for row, vec in zip(intents, vectors):
                row.embedding = vec
            await session.commit()

        logger.info(
            "Embedded: products=%s companies=%s cases=%s intents=%s",
            n_products,
            n_companies,
            n_cases,
            len(intents),
        )


if __name__ == "__main__":
    asyncio.run(main())
