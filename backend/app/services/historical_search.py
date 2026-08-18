"""Semantic search over historical PROSTOR calcs via pgvector.

Uses cosine distance (`<=>` operator) against the HNSW index on
`historical_cases.embedding`. Handles the case where embeddings are
still being backfilled by simply returning fewer results.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.db import Company, HistoricalCase, Product
from backend.app.services.embeddings import get_embeddings_service


@dataclass(frozen=True)
class SimilarCase:
    id: str
    title: str
    summary: str
    object_name: str
    product_id: str
    product_name: str | None
    company_id: str | None
    company_name: str | None
    similarity: float  # 1 - cosine_distance, higher = more similar


class HistoricalSearchService:
    async def similar_cases(
        self,
        session: AsyncSession,
        query: str,
        limit: int = 5,
        min_similarity: float = 0.30,
    ) -> list[SimilarCase]:
        query = (query or "").strip()
        if not query:
            return []

        vector = get_embeddings_service().embed_query(query)

        # pgvector cosine distance via <=> operator (needs HNSW vector_cosine_ops index).
        distance = HistoricalCase.embedding.cosine_distance(vector).label("distance")

        stmt = (
            select(
                HistoricalCase.id,
                HistoricalCase.title,
                HistoricalCase.summary,
                HistoricalCase.object_name,
                HistoricalCase.product_id,
                HistoricalCase.company_id,
                Product.name.label("product_name"),
                Company.name.label("company_name"),
                distance,
            )
            .join(Product, Product.id == HistoricalCase.product_id, isouter=True)
            .join(Company, Company.id == HistoricalCase.company_id, isouter=True)
            .where(HistoricalCase.embedding.isnot(None))
            .order_by(distance.asc())
            .limit(limit)
        )

        rows = (await session.execute(stmt)).mappings().all()

        out: list[SimilarCase] = []
        for r in rows:
            similarity = max(0.0, 1.0 - float(r["distance"]))
            if similarity < min_similarity:
                continue
            out.append(
                SimilarCase(
                    id=r["id"],
                    title=r["title"] or "",
                    summary=r["summary"] or "",
                    object_name=r["object_name"] or "",
                    product_id=r["product_id"],
                    product_name=r["product_name"],
                    company_id=r["company_id"],
                    company_name=r["company_name"],
                    similarity=round(similarity, 3),
                )
            )
        return out


historical_search_service = HistoricalSearchService()
