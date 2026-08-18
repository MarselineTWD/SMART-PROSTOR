"""Чат, привязанный к документу ТЗ: белый список полей и применение правок.

Определяет, какие поля ИИ разрешено заполнять (:meth:`allowed_fields`), и
раскладывает извлечённые значения по «правильным местам» документа
(:meth:`apply`): реквизиты верхнего уровня, исходные данные, доп. реквизиты
шаблона и содержимое разделов — согласованно с валидацией и генератором.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import uuid4

from backend.app.models.domain import (
    TZChatMessage,
    TZDocument,
    TZFieldUpdate,
    TZTemplate,
)
from backend.app.schemas.assistant import AllowedField


# Канонические места хранения (совпадают с tz_validation и tz_generator).
DOCUMENT_FIELDS: dict[str, str] = {
    "object_name": "Объект работ",
    "customer_name": "Заказчик",
    "executor_name": "Исполнитель",
    "contract_name": "Договор",
    "title": "Название ТЗ",
}
INPUT_DATA_FIELDS: list[tuple[str, str, str]] = [
    ("goal", "Цель работ", "textarea"),
    ("deadline", "Плановый срок", "date"),
    ("source_data_ready", "Исходные данные готовы", "checkbox"),
    ("needs_3d_model", "Нужна 3D-модель", "checkbox"),
    ("requires_subcontractor", "Требуется субподряд", "checkbox"),
    ("subcontract_share_percent", "Доля субподряда, %", "number"),
    ("separate_subcontract_estimate", "Отдельный РС субподряда", "checkbox"),
]

_BOOL_INPUT = {
    "source_data_ready",
    "needs_3d_model",
    "requires_subcontractor",
    "separate_subcontract_estimate",
}
_INPUT_KEYS = {key for key, _, _ in INPUT_DATA_FIELDS}
_TRUE = {"true", "1", "да", "yes", "истина", "требуется", "нужен", "нужна", "готов", "готовы"}
_FALSE = {"false", "0", "нет", "no", "ложь", "не требуется", "не нужен", "не готов"}


class TZChatService:
    def allowed_fields(self, document: TZDocument, template: TZTemplate) -> list[AllowedField]:
        fields = [
            AllowedField(target="document", key=key, label=label)
            for key, label in DOCUMENT_FIELDS.items()
        ]
        fields += [
            AllowedField(target="input_data", key=key, label=label, type=field_type)
            for key, label, field_type in INPUT_DATA_FIELDS
        ]
        covered = set(DOCUMENT_FIELDS) | _INPUT_KEYS | {"stages"}
        for field in template.fields:
            if field.key in covered:
                continue
            fields.append(
                AllowedField(
                    target="requisites",
                    key=field.key,
                    label=field.label,
                    type=field.input_type,
                )
            )
        for section in template.sections:
            fields.append(
                AllowedField(target="section", key=section.key, label=section.title, type="textarea")
            )
        return fields

    def apply(
        self,
        document: TZDocument,
        template: TZTemplate,
        updates: list[TZFieldUpdate],
    ) -> tuple[list[TZFieldUpdate], list[TZFieldUpdate]]:
        allowed = {(a.target, a.key): a for a in self.allowed_fields(document, template)}
        applied: list[TZFieldUpdate] = []
        skipped: list[TZFieldUpdate] = []
        for update in updates:
            target = allowed.get((update.target, update.key))
            if target is None or self._is_empty(update.value):
                skipped.append(update)
                continue
            if self._write(document, update, target):
                update.applied = True
                applied.append(update)
            else:
                skipped.append(update)
        if applied:
            document.updated_at = datetime.now(timezone.utc)
        return applied, skipped

    def make_message(
        self,
        role: str,
        text: str,
        *,
        suggestions: list[str] | None = None,
        field_updates: list[TZFieldUpdate] | None = None,
        warnings: list[str] | None = None,
    ) -> TZChatMessage:
        return TZChatMessage(
            id=f"m-{uuid4().hex[:8]}",
            role=role,
            text=text,
            created_at=datetime.now(timezone.utc),
            suggestions=suggestions or [],
            field_updates=field_updates or [],
            warnings=warnings or [],
        )

    # --- Запись значения в нужное место документа ----------------------------

    def _write(self, document: TZDocument, update: TZFieldUpdate, allowed: AllowedField) -> bool:
        try:
            if update.target == "document":
                setattr(document, update.key, _as_text(update.value))
                return True
            if update.target == "input_data":
                return self._write_input(document, update.key, update.value)
            if update.target == "requisites":
                document.requisites[update.key] = _coerce_req(allowed.type, update.value)
                return True
            if update.target == "section":
                for section in document.sections:
                    if section.key == update.key:
                        section.content = _as_text(update.value)
                        section.source = "ai"
                        return True
                return False
        except (TypeError, ValueError):
            return False
        return False

    def _write_input(self, document: TZDocument, key: str, value: object) -> bool:
        if key in _BOOL_INPUT:
            setattr(document.input_data, key, _as_bool(value))
            return True
        if key == "subcontract_share_percent":
            pct = _as_int(value)
            if pct is None:
                return False
            setattr(document.input_data, key, max(0, min(100, pct)))
            return True
        setattr(document.input_data, key, _as_text(value))
        return True

    @staticmethod
    def _is_empty(value: object) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())


def _as_text(value: object) -> str:
    return str(value).strip()


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return _as_text(value).lower() in _TRUE


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    match = re.search(r"-?\d+", str(value))
    return int(match.group()) if match else None


def _coerce_req(field_type: str, value: object) -> object:
    if field_type == "checkbox":
        return _as_bool(value)
    if field_type == "number":
        number = _as_int(value)
        return number if number is not None else _as_text(value)
    return _as_text(value)


tz_chat_service = TZChatService()
