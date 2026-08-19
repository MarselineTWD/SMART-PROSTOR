"""Услуги и календарный план ТЗ: правила БД + опциональная доработка LLM."""
from __future__ import annotations

import json
import re
from typing import Any

from backend.app.models.domain import TZDocument, TZTemplate
from backend.app.services.llm import llm_complete_json


def _clean_name(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" .;,-")[:180]


def normalize_services(value: object) -> list[dict[str, Any]]:
    """Приводит ручной/ИИ-ввод к стабильному формату хранения."""
    if isinstance(value, str):
        value = [part for part in re.split(r"[\n;]+", value) if part.strip()]
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in value:
        item = raw if isinstance(raw, dict) else {"name": raw}
        name = _clean_name(item.get("name"))
        marker = name.casefold()
        if not name or marker in seen:
            continue
        seen.add(marker)
        result.append({
            "name": name,
            "mandatory": bool(item.get("mandatory", False)),
            "source": str(item.get("source") or "manual"),
            "reason": _clean_name(item.get("reason")),
            **({"product_id": str(item["product_id"])} if item.get("product_id") else {}),
        })
    return result[:30]


def _automatic_services(document: TZDocument, template: TZTemplate) -> list[dict[str, Any]]:
    data = document.input_data
    items: list[dict[str, Any]] = [{
        "name": template.name,
        "mandatory": True,
        "source": "database",
        "reason": "Основная услуга выбранного шаблона ТЗ",
        **({"product_id": document.product_id or template.product_id} if document.product_id or template.product_id else {}),
    }]
    if not data.source_data_ready:
        items.append({
            "name": "Аудит, сбор и нормализация исходных данных",
            "mandatory": True,
            "source": "rule",
            "reason": "Исходные данные не отмечены как готовые",
        })
    if data.needs_3d_model:
        items.append({
            "name": "Построение и проверка 3D-модели",
            "mandatory": True,
            "source": "rule",
            "reason": "В параметрах ТЗ указана необходимость 3D-модели",
        })
    if data.requires_subcontractor and data.separate_subcontract_estimate:
        items.append({
            "name": "Подготовка отдельного расчёта стоимости субподряда",
            "mandatory": True,
            "source": "rule",
            "reason": "Для субподряда требуется отдельный расчёт стоимости",
        })
    return normalize_services(items)


def sync_services(document: TZDocument, template: TZTemplate) -> list[dict[str, Any]]:
    """Добавляет обязательные услуги, уважая удалённые пользователем позиции."""
    existing = normalize_services(document.requisites.get("services"))
    removed = {
        _clean_name(item).casefold()
        for item in document.requisites.get("removed_auto_services", [])
        if _clean_name(item)
    }
    by_name = {item["name"].casefold(): item for item in existing}
    for item in _automatic_services(document, template):
        marker = item["name"].casefold()
        if marker not in by_name and marker not in removed:
            existing.append(item)
            by_name[marker] = item
    document.requisites["services"] = existing
    return existing


def _fallback_stages(document: TZDocument, template: TZTemplate, services: list[dict[str, Any]]) -> list[str]:
    stages: list[str] = []
    if not document.input_data.source_data_ready:
        stages.append("Сбор, аудит и подготовка исходных данных")
    else:
        stages.append("Проверка и систематизация исходных данных")

    for item in services:
        name = item["name"]
        if name.casefold() == template.name.casefold():
            stages.extend(template.stage_presets[1:-1] or template.stage_presets)
        elif "исходн" not in name.casefold() and "расчёт стоимости" not in name.casefold():
            stages.append(name)

    complexity = any(
        document.requisites.get(key)
        for key in ("scenario_count", "well_count", "concept_variants", "target_horizons")
    ) or document.input_data.needs_3d_model
    if complexity:
        stages.append("Контроль качества и согласование промежуточных результатов")
    if document.input_data.requires_subcontractor:
        stages.append("Координация и приёмка результатов субподрядных работ")
    stages.append("Подготовка, согласование и передача итоговых материалов")

    result: list[str] = []
    seen: set[str] = set()
    for stage in stages:
        name = _clean_name(stage)
        if name and name.casefold() not in seen:
            seen.add(name.casefold())
            result.append(name)
    return result[:14]


def generate_plan(
    document: TZDocument,
    template: TZTemplate,
    *,
    instruction: str | None = None,
    knowledge_conditions: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Формирует переменный план; при недоступности LLM действует объяснимый fallback."""
    services = sync_services(document, template)
    fallback = _fallback_stages(document, template, services)
    context = {
        "template": template.name,
        "goal": document.input_data.goal,
        "deadline": document.input_data.deadline,
        "services": services,
        "parameters": document.requisites,
        "input_data": document.input_data.model_dump(),
        "schedule_constraints": document.requisites.get("schedule_constraints", []),
        "database_conditions": knowledge_conditions or [],
        "baseline": fallback,
        "instruction": instruction,
    }
    response = llm_complete_json(
        "Ты составляешь реалистичный календарный план нефтегазового ТЗ. Верни только JSON "
        '{"stages":["..."]}. Количество этапов определяется составом услуг и сложностью. '
        "Включи все выбранные услуги. Учти обязательные условия и паузы из БД, но сами паузы "
        "не превращай в работы: они отображаются отдельно. Не придумывай даты и стоимость.",
        json.dumps(context, ensure_ascii=False, default=str),
        temperature=0.15,
        max_tokens=1000,
    )
    candidate = response.get("stages") if isinstance(response, dict) else None
    if isinstance(candidate, list):
        cleaned = [_clean_name(item) for item in candidate]
        cleaned = list(dict.fromkeys(item for item in cleaned if item))[:14]
        if len(cleaned) >= 2:
            document.requisites["stages"] = cleaned
            document.requisites["plan_source"] = "ai"
            return cleaned
    document.requisites["stages"] = fallback
    document.requisites["plan_source"] = "rules+database"
    return fallback
