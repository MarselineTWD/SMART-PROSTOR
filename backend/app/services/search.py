"""Hybrid product search: pgvector cosine similarity + business signals.

The public API is intentionally identical to the previous mocks-based
implementation — same `SearchContext`/`SearchResult` shape — so the
frontend and other services keep working without changes.

Signals combined into the final score:
* semantic similarity (cosine on multilingual-e5-small embeddings),
* keyword overlap on name + summary + keywords + synonyms,
* active contracts, operations, prices, historical cases per product,
* top company rating.

If embeddings are still being backfilled by `embed_seeds` on first
startup, the service degrades gracefully to keyword-only ranking on
the in-memory catalog snapshot — search stays usable end-to-end from
the very first request.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import db as orm
from backend.app.models.domain import (
    IntentType,
    Product,
    SearchContext,
    SearchResult,
)
from backend.app.services.catalog import catalog_service
from backend.app.services.embeddings import get_embeddings_service


INTENT_KEYWORDS: dict[IntentType, set[str]] = {
    "service_search": {"найти", "нужно", "услуга", "сервис", "оценить", "подобрать"},
    "contractor_selection": {"исполнитель", "подрядчик", "компания", "кто", "кому"},
    "similar_cases": {"аналог", "пример", "похож", "кейс"},
    "draft_generation": {"тз", "техзадание", "сформировать", "заявка", "черновик"},
}

# Weights for the hybrid score.
W_SEMANTIC = 0.70
W_BUSINESS = 0.30
CANDIDATE_POOL = 20  # top-K products fetched from pgvector before rerank


class SearchService:
    async def search(
        self,
        session: AsyncSession,
        query: str,
        limit: int = 3,
    ) -> SearchContext:
        query = (query or "").strip()
        if not query:
            return SearchContext(query="", detected_intent="service_search", products=[])

        tokens = set(self._tokenize(query))
        query_vector: list[float] | None = None
        try:
            query_vector = get_embeddings_service().embed_query(query)
        except Exception:
            query_vector = None  # graceful fallback if model unavailable

        detected_intent = await self._detect_intent(session, query, tokens, query_vector)

        semantic_scores: dict[str, float] = {}
        semantic_case_pool: list[dict] = []

        if query_vector is not None:
            semantic_scores = await self._semantic_product_scores(session, query_vector)
            semantic_case_pool = await self._semantic_case_pool(session, query_vector)

        results = self._rank_products(
            query=query,
            tokens=tokens,
            semantic_scores=semantic_scores,
            semantic_cases=semantic_case_pool,
            limit=limit,
        )

        recommendations = self._recommendations(detected_intent)

        return SearchContext(
            query=query,
            detected_intent=detected_intent,
            products=results,
            recommendations=recommendations,
        )

    # ----- intent -----------------------------------------------------------

    async def _detect_intent(
        self,
        session: AsyncSession,
        query: str,
        tokens: set[str],
        query_vector: list[float] | None,
    ) -> IntentType:
        if query_vector is not None:
            distance = orm.IntentPrompt.embedding.cosine_distance(query_vector).label("d")
            stmt = (
                select(orm.IntentPrompt.intent, distance)
                .where(orm.IntentPrompt.embedding.isnot(None))
                .order_by(distance.asc())
                .limit(1)
            )
            row = (await session.execute(stmt)).first()
            if row is not None:
                intent, dist = row
                # 1 - cos_dist is similarity in [0, 1]; require >0.35 to trust.
                if dist is not None and (1.0 - float(dist)) >= 0.35:
                    return intent  # type: ignore[return-value]

        # keyword fallback
        scores = {
            intent: len(tokens & keywords)
            for intent, keywords in INTENT_KEYWORDS.items()
        }
        return max(scores, key=scores.get) if any(scores.values()) else "service_search"

    # ----- semantic pools ---------------------------------------------------

    async def _semantic_product_scores(
        self, session: AsyncSession, query_vector: list[float]
    ) -> dict[str, float]:
        distance = orm.Product.embedding.cosine_distance(query_vector).label("d")
        stmt = (
            select(orm.Product.id, distance)
            .where(orm.Product.embedding.isnot(None))
            .order_by(distance.asc())
            .limit(CANDIDATE_POOL)
        )
        rows = (await session.execute(stmt)).all()
        return {pid: max(0.0, 1.0 - float(dist)) for pid, dist in rows}

    async def _semantic_case_pool(
        self, session: AsyncSession, query_vector: list[float]
    ) -> list[dict]:
        distance = orm.HistoricalCase.embedding.cosine_distance(query_vector).label("d")
        stmt = (
            select(
                orm.HistoricalCase.id,
                orm.HistoricalCase.product_id,
                distance,
            )
            .where(orm.HistoricalCase.embedding.isnot(None))
            .order_by(distance.asc())
            .limit(20)
        )
        rows = (await session.execute(stmt)).mappings().all()
        return [
            {
                "id": r["id"],
                "product_id": r["product_id"],
                "similarity": max(0.0, 1.0 - float(r["d"])),
            }
            for r in rows
        ]

    # ----- ranking ----------------------------------------------------------

    def _rank_products(
        self,
        query: str,
        tokens: set[str],
        semantic_scores: dict[str, float],
        semantic_cases: list[dict],
        limit: int,
    ) -> list[SearchResult]:
        products = catalog_service.list_products()
        if not products:
            return []

        # semantic candidates first; if none (embeddings not ready), fall back
        # to the whole catalog and rely on keyword overlap.
        if semantic_scores:
            candidate_products = [p for p in products if p.id in semantic_scores]
        else:
            candidate_products = products

        cases_by_product: dict[str, list[dict]] = {}
        for c in semantic_cases:
            cases_by_product.setdefault(c["product_id"], []).append(c)

        scored: list[tuple[float, SearchResult]] = []
        for product in candidate_products:
            sem = semantic_scores.get(product.id, 0.0)

            overlap = tokens & self._product_terms(product)
            keyword_boost = min(len(overlap), 4) / 4.0  # normalize to [0,1]

            reasons: list[str] = []
            if sem > 0:
                reasons.append(f"Семантическая близость {sem:.2f} (cosine).")
            if overlap:
                reasons.append(f"Совпали ключевые термины: {', '.join(sorted(overlap))}.")

            bus_signals = self._business_signals(product, reasons)
            companies = catalog_service.list_product_companies(product.id)

            top_rating = companies[0].rating if companies else 0.0
            bus = min(
                1.0,
                bus_signals
                + 0.05 * (top_rating / 5.0)
                + 0.05 * min(len(cases_by_product.get(product.id, [])), 3),
            )

            total = (
                W_SEMANTIC * (0.85 * sem + 0.15 * keyword_boost)
                + W_BUSINESS * bus
            )

            # Skip completely irrelevant items (no semantic and no overlap).
            if sem == 0 and not overlap:
                continue

            if companies:
                top = companies[0]
                reasons.append(
                    f"Доступен сильный исполнитель: {top.name} (рейтинг {top.rating:.1f})."
                )

            similar_case_objs = self._pick_similar_cases(product.id, cases_by_product)

            scored.append(
                (
                    total,
                    SearchResult(
                        product=product,
                        score=round(total, 3),
                        reasons=reasons,
                        recommended_companies=companies[:3],
                        similar_cases=similar_case_objs[:2],
                    ),
                )
            )

        scored.sort(key=lambda item: item[0], reverse=True)
        shortlisted = [item for _, item in scored[:limit]]

        if shortlisted:
            return shortlisted

        # Nothing matched — offer top products by contract density as a hint.
        return self._fallback_results(limit)

    def _pick_similar_cases(
        self, product_id: str, cases_by_product: dict[str, list[dict]]
    ) -> list:
        semantic_hits = cases_by_product.get(product_id, [])
        semantic_hits.sort(key=lambda c: c["similarity"], reverse=True)
        hit_ids = {c["id"] for c in semantic_hits}
        # Merge with catalog-known cases as fallback if the semantic pool
        # returned nothing for this product yet.
        result = []
        for c in semantic_hits:
            case = self._find_case(c["id"])
            if case is not None:
                result.append(case)
        if not result:
            result = catalog_service.list_historical_cases(product_id)
        return result

    @staticmethod
    def _find_case(case_id: str):
        for p in catalog_service.list_products():
            for c in catalog_service.list_historical_cases(p.id):
                if c.id == case_id:
                    return c
        return None

    def _fallback_results(self, limit: int) -> list[SearchResult]:
        fallback = sorted(
            catalog_service.list_products(),
            key=lambda p: len(p.active_contract_ids),
            reverse=True,
        )[:limit]
        return [
            SearchResult(
                product=p,
                score=0.5,
                reasons=[
                    "Точного совпадения не найдено — показан наиболее востребованный продукт."
                ],
                recommended_companies=catalog_service.list_product_companies(p.id)[:3],
                similar_cases=catalog_service.list_historical_cases(p.id)[:2],
            )
            for p in fallback
        ]

    # ----- helpers ----------------------------------------------------------

    @staticmethod
    def _business_signals(product: Product, reasons: list[str]) -> float:
        score = 0.0
        if product.active_contract_ids:
            score += 0.15
            reasons.append(
                f"Есть активные договоры ({len(product.active_contract_ids)})."
            )
        if product.has_operations:
            score += 0.05
        if product.has_price_rules:
            score += 0.05
            reasons.append("Есть расценки для расчёта стоимости.")
        return score

    @staticmethod
    def _product_terms(product: Product) -> set[str]:
        blob = " ".join(
            [
                product.name,
                product.summary,
                *product.keywords,
                *product.synonyms,
                *product.operations,
            ]
        )
        return set(SearchService._tokenize(blob))

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        normalized = re.sub(r"[^0-9A-Za-zА-Яа-яЁё]+", " ", text.lower())
        return [token for token in normalized.split() if token]

    def _recommendations(self, intent: IntentType) -> list[str]:
        base = [
            "Сузьте объект и ожидаемый результат, чтобы точнее подобрать шаблон ТЗ.",
            "Выберите исполнителя до генерации черновика — сразу проверим правила субподряда.",
        ]
        if intent == "draft_generation":
            base.append(
                "После выбора продукта можно сразу перейти к предзаполненному RequestDraft."
            )
        return base


search_service = SearchService()
