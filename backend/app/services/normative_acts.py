"""Sync + async accessors for the normative acts catalog.

Two use-cases:
* `tz_generator` builds the "Требования к работе" section synchronously →
  uses the in-memory snapshot populated at app startup via `refresh(session)`.
* API / semantic recommendations run async against pgvector.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import db as orm
from backend.app.services.embeddings import get_embeddings_service


@dataclass(frozen=True)
class NormativeAct:
    id: str
    document_type: str
    authority: str | None
    number: str | None
    date_issued: date | None
    title: str
    short_title: str
    url: str | None
    is_active: bool


class NormativeActService:
    def __init__(self) -> None:
        self._acts_by_id: dict[str, NormativeAct] = {}
        self._by_template: dict[str, list[str]] = {}
        self._loaded = False

    # -- lifecycle -----------------------------------------------------------

    async def refresh(self, session: AsyncSession) -> None:
        acts_orm = (await session.execute(select(orm.NormativeAct))).scalars().all()
        links_orm = (
            await session.execute(
                select(orm.TemplateNormativeAct).order_by(
                    orm.TemplateNormativeAct.sort_order
                )
            )
        ).scalars().all()

        self._acts_by_id = {
            a.id: NormativeAct(
                id=a.id,
                document_type=a.document_type or "Прочее",
                authority=a.authority,
                number=a.number,
                date_issued=a.date_issued,
                title=a.title,
                short_title=a.short_title or a.title[:120],
                url=a.url,
                is_active=bool(a.is_active),
            )
            for a in acts_orm
        }
        by_template: dict[str, list[str]] = {}
        for link in links_orm:
            by_template.setdefault(link.template_key, []).append(link.act_id)
        self._by_template = by_template
        self._loaded = True

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # -- sync reads ----------------------------------------------------------

    def acts_for_template(self, template_key: str) -> list[NormativeAct]:
        ids = self._by_template.get(template_key, [])
        return [self._acts_by_id[i] for i in ids if i in self._acts_by_id]

    def all_acts(self) -> list[NormativeAct]:
        return list(self._acts_by_id.values())

    # -- async pgvector: подбор релевантных актов ----------------------------

    async def similar_acts(
        self,
        session: AsyncSession,
        query: str,
        limit: int = 5,
        min_similarity: float = 0.35,
    ) -> list[tuple[NormativeAct, float]]:
        query = (query or "").strip()
        if not query:
            return []
        vector = get_embeddings_service().embed_query(query)
        distance = orm.NormativeAct.embedding.cosine_distance(vector).label("d")
        stmt = (
            select(orm.NormativeAct.id, distance)
            .where(orm.NormativeAct.embedding.isnot(None))
            .where(orm.NormativeAct.is_active.is_(True))
            .order_by(distance.asc())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()
        out: list[tuple[NormativeAct, float]] = []
        for act_id, dist in rows:
            similarity = max(0.0, 1.0 - float(dist))
            if similarity < min_similarity:
                continue
            act = self._acts_by_id.get(act_id)
            if act is not None:
                out.append((act, round(similarity, 3)))
        return out


normative_act_service = NormativeActService()
