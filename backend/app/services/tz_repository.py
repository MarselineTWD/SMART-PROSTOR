"""Хранилище сохранённых ТЗ.

Основной бэкенд — PostgreSQL (таблица ``tz_documents``, создаётся миграцией
0002). Если БД недоступна (например, локальный запуск без Docker), репозиторий
прозрачно переключается на хранилище в памяти процесса, чтобы страница
«Мои ТЗ» продолжала работать в демо-режиме.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.db import SessionLocal
from backend.app.models.db import TZDocumentORM
from backend.app.models.domain import TZDocument, TZDocumentSection


logger = logging.getLogger(__name__)

# Фолбэк-хранилище в памяти процесса.
_MEMORY: dict[str, TZDocument] = {}
_use_memory = False


def _to_columns(doc: TZDocument) -> dict:
    return {
        "id": doc.id,
        "template_key": doc.template_key,
        "template_name": doc.template_name,
        "product_id": doc.product_id,
        "title": doc.title,
        "object_name": doc.object_name,
        "customer_name": doc.customer_name,
        "executor_name": doc.executor_name,
        "contract_name": doc.contract_name,
        "status": doc.status,
        "ready_score": doc.ready_score,
        "requisites": doc.requisites,
        "input_data": doc.input_data.model_dump(),
        "sections": [s.model_dump() for s in doc.sections],
        "notes": doc.notes,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
    }


def _from_orm(row: TZDocumentORM) -> TZDocument:
    return TZDocument(
        id=row.id,
        template_key=row.template_key,
        template_name=row.template_name or "",
        product_id=row.product_id,
        title=row.title or "",
        object_name=row.object_name,
        customer_name=row.customer_name,
        executor_name=row.executor_name,
        contract_name=row.contract_name,
        status=row.status or "draft",
        ready_score=row.ready_score or 0,
        requisites=row.requisites or {},
        input_data=row.input_data or {},
        sections=[TZDocumentSection(**s) for s in (row.sections or [])],
        notes=row.notes or [],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class TZRepository:
    async def create(self, doc: TZDocument) -> TZDocument:
        global _use_memory
        if not _use_memory:
            try:
                async with SessionLocal() as session:
                    session.add(TZDocumentORM(**_to_columns(doc)))
                    await session.commit()
                return doc
            except SQLAlchemyError as exc:  # БД недоступна -> память
                self._degrade(exc)
        _MEMORY[doc.id] = doc
        return doc

    async def list(self) -> list[TZDocument]:
        global _use_memory
        if not _use_memory:
            try:
                async with SessionLocal() as session:
                    result = await session.execute(
                        select(TZDocumentORM).order_by(TZDocumentORM.updated_at.desc())
                    )
                    return [_from_orm(row) for row in result.scalars()]
            except SQLAlchemyError as exc:
                self._degrade(exc)
        return sorted(
            _MEMORY.values(),
            key=lambda d: d.updated_at or d.created_at or "",
            reverse=True,
        )

    async def get(self, doc_id: str) -> TZDocument | None:
        global _use_memory
        if not _use_memory:
            try:
                async with SessionLocal() as session:
                    row = await session.get(TZDocumentORM, doc_id)
                    return _from_orm(row) if row else None
            except SQLAlchemyError as exc:
                self._degrade(exc)
        return _MEMORY.get(doc_id)

    async def update(self, doc: TZDocument) -> TZDocument:
        global _use_memory
        if not _use_memory:
            try:
                async with SessionLocal() as session:
                    row = await session.get(TZDocumentORM, doc.id)
                    if row is None:
                        session.add(TZDocumentORM(**_to_columns(doc)))
                    else:
                        for key, value in _to_columns(doc).items():
                            setattr(row, key, value)
                    await session.commit()
                return doc
            except SQLAlchemyError as exc:
                self._degrade(exc)
        _MEMORY[doc.id] = doc
        return doc

    async def delete(self, doc_id: str) -> bool:
        global _use_memory
        if not _use_memory:
            try:
                async with SessionLocal() as session:
                    row = await session.get(TZDocumentORM, doc_id)
                    if row is None:
                        return False
                    await session.delete(row)
                    await session.commit()
                    return True
            except SQLAlchemyError as exc:
                self._degrade(exc)
        return _MEMORY.pop(doc_id, None) is not None

    @staticmethod
    def _degrade(exc: Exception) -> None:
        global _use_memory
        if not _use_memory:
            logger.warning("БД недоступна, ТЗ хранятся в памяти процесса: %s", exc)
            _use_memory = True


tz_repository = TZRepository()
