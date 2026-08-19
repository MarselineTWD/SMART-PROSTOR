"""Контекст ассистента: каталог, полные черновики и особые условия из БД."""
from __future__ import annotations

import re
from typing import Any

from backend.app.services.catalog import catalog_service
from backend.app.services.search import search_service
from backend.app.services.tz_repository import tz_repository
from backend.app.services.tz_templates import tz_template_service


_SPECIAL_KEYS = (
    "condition", "constraint", "restriction", "risk", "special", "exception",
    "услов", "огранич", "риск", "особ", "исключ", "pause", "приостан",
)
_SPECIAL_SECTIONS = {"conditions", "other", "subcontractors", "work_requirements"}
_INTENT_LABELS = {
    "service_search": "Подбор услуги",
    "contractor_selection": "Подбор исполнителя",
    "similar_cases": "Поиск аналогичных ТЗ",
    "draft_generation": "Формирование технического задания",
}
_SUBCONTRACT_LABELS = {
    "allowed": "субподряд разрешён",
    "limit_70": "субподряд — не более 70%",
    "forbidden": "субподряд запрещён",
    "separate_rs_required": "для субподряда нужен отдельный РС",
}


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[а-яёa-z0-9]+", (value or "").lower()))


def _short(value: Any, limit: int = 700) -> Any:
    if isinstance(value, str):
        return value.strip()[:limit]
    if isinstance(value, list):
        return [_short(item, 300) for item in value[:8]]
    if isinstance(value, dict):
        return {str(key): _short(item, 300) for key, item in list(value.items())[:12]}
    return value


def collect_exceptional_conditions(documents: list, query: str) -> list[dict]:
    """Извлекает редкие/особые условия из ранее созданных ТЗ с указанием источника."""
    query_tokens = _tokens(query)
    rows: list[tuple[int, str, dict]] = []
    for document in documents:
        document_tokens = _tokens(" ".join(filter(None, [
            document.title, document.template_name, document.object_name or "",
            document.input_data.goal or "",
        ])))
        relevance = len(query_tokens & document_tokens)
        source = {
            "source_tz_id": document.id,
            "source_tz_title": document.title or document.template_name,
            "relevance": relevance,
        }
        for key, value in (document.requisites or {}).items():
            if not value:
                continue
            normalized = str(key).lower()
            if key == "schedule_constraints" or any(marker in normalized for marker in _SPECIAL_KEYS):
                rows.append((relevance, str(document.updated_at or ""), {
                    **source, "field": f"requisites.{key}", "value": _short(value),
                }))
        for section in document.sections:
            if section.key in _SPECIAL_SECTIONS and section.content.strip():
                rows.append((relevance, str(document.updated_at or ""), {
                    **source, "field": f"section.{section.key}", "value": _short(section.content),
                }))
        if document.input_data.needs_3d_model or document.input_data.requires_subcontractor:
            rows.append((relevance, str(document.updated_at or ""), {
                **source,
                "field": "input_data.exceptional_flags",
                "value": {
                    "needs_3d_model": document.input_data.needs_3d_model,
                    "requires_subcontractor": document.input_data.requires_subcontractor,
                    "subcontract_share_percent": document.input_data.subcontract_share_percent,
                    "separate_subcontract_estimate": document.input_data.separate_subcontract_estimate,
                },
            }))
    rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [row[2] for row in rows[:12]]


def _filling_recommendations(document: dict, product_id: str | None) -> list[dict]:
    input_data = document.get("input_data") or {}
    requisites = document.get("requisites") or {}
    rows: list[dict] = []

    def add(field: str, label: str, recommendation: str, priority: str = "medium") -> None:
        rows.append({
            "field": field, "label": label, "recommendation": recommendation,
            "priority": priority,
        })

    if not document.get("object_name"):
        add("document.object_name", "Объект работ", "Укажите месторождение, участок или номер скважины.", "high")
    if not input_data.get("goal"):
        add("input_data.goal", "Цель", "Зафиксируйте ожидаемый результат и назначение подсчёта.", "high")
    if not input_data.get("deadline"):
        add("input_data.deadline", "Срок", "Укажите требуемую дату готовности и дату защиты.")
    if not requisites.get("city"):
        add("requisites.city", "Место выполнения", "Укажите офисный или полевой формат и регион — это влияет на цену.")
    if not requisites.get("stages"):
        add("requisites.stages", "Этапы", "Добавьте подготовку данных, моделирование/подсчёт, проверку и отчётность.", "high")

    if product_id == "product-reserves":
        reserve_specific = [
            ("requisites.target_horizons", "Целевые горизонты", "Перечислите пласты и границы подсчёта."),
            ("requisites.reserve_category", "Категории запасов", "Укажите категории и дату, на которую фиксируются запасы."),
            ("requisites.reserve_standard", "Стандарт и экспертиза", "Укажите ГКЗ/ТКЗ, PRMS или корпоративный стандарт."),
            ("input_data.initial_data", "Исходные данные", "Перечислите ГИС, сейсмику, керн, испытания и действующие модели."),
        ]
        for field, label, recommendation in reserve_specific:
            target = input_data if field.startswith("input_data.") else requisites
            key = field.split(".", 1)[1]
            if not target.get(key):
                add(field, label, recommendation, "high" if "horizons" in field else "medium")
    return rows[:8]


def _conditional_services(query: str, document: dict, product_id: str | None) -> list[dict]:
    text = query.lower()
    input_data = document.get("input_data") or {}
    rows: list[dict] = []

    def add(name: str, status: str, condition: str, reason: str) -> None:
        rows.append({"name": name, "status": status, "condition": condition, "reason": reason})

    if product_id == "product-reserves":
        add(
            "Интерпретация ГИС и контроль качества скважинных данных",
            "рекомендуется",
            "Для подсчёта по скважине или при неоднородных исходных данных",
            "Ошибки в петрофизике напрямую меняют объёмы и категории запасов.",
        )
        add(
            "Геологическое моделирование / актуализация 3D-модели",
            "может быть обязательной",
            "Если запасы считаются объёмным методом или действующая модель устарела",
            "Модель задаёт геометрию залежи и распределение подсчётных параметров.",
        )
        add(
            "Сопровождение государственной экспертизы запасов",
            "может быть обязательной",
            "Если результат должен пройти ГКЗ/ТКЗ или изменить государственный баланс",
            "Потребуются комплект отчётности, ответы на замечания и защита материалов.",
        )
    if not input_data.get("source_data_ready", False):
        add(
            "Аудит, оцифровка и нормализация исходных данных",
            "обязательна до расчёта",
            "Исходные данные не отмечены как готовые",
            "Без проверки полноты и качества итоговый подсчёт ненадёжен.",
        )
    if any(word in text for word in ("керн", "флюид", "лаборатор", "образц")):
        add(
            "Исследования керна и пластовых флюидов",
            "может быть обязательной",
            "Если подсчётные параметры нельзя подтвердить имеющимися исследованиями",
            "Лабораторные данные уточняют пористость, насыщенность и свойства флюидов.",
        )
    if input_data.get("requires_subcontractor") and input_data.get("separate_subcontract_estimate"):
        add(
            "Отдельный расчёт стоимости субподрядных работ",
            "обязателен",
            "В ТЗ включён субподряд с отдельным РС",
            "Стоимость и объём субподряда должны быть выделены отдельно.",
        )
    return rows[:6]


def _build_discovery(search, historical: list[tuple], enriched: dict) -> dict:
    top = search.products[0] if search.products else None
    product_id = top.product.id if top else None
    services = []
    for result in search.products[:3]:
        template = tz_template_service.template_for_product(result.product.id)
        overlap = len(
            search_service._query_tokens(search.query)
            & search_service._product_terms(result.product)
        )
        services.append({
            "product_id": result.product.id,
            "name": result.product.name,
            "summary": result.product.summary,
            "score": min(0.98, 0.55 + overlap * 0.07) if overlap else max(0.35, result.score),
            "reasons": result.reasons[:4],
            "template_key": template.key,
            "template_name": template.name,
        })

    if product_id == "product-reserves":
        products = catalog_service.list_products()
        related = []
        geology = next((item for item in products if item.id == "product-geology"), None)
        if geology:
            related.append((geology, 0.82, [
                "Связана с построением геологической основы для подсчёта запасов.",
                "Нужна, если требуется актуализировать концепцию залежи или модель объекта.",
            ]))
        laboratory = max(
            (item for item in products if "исследования пластовых систем" in item.name.lower()),
            key=lambda item: len(item.active_contract_ids),
            default=None,
        )
        if laboratory:
            related.append((laboratory, 0.74, [
                "Уточняет подсчётные параметры по керну и пластовым флюидам.",
                "Становится необходимой при недостаточности лабораторных данных.",
            ]))
        services = services[:1]
        for product, score, reasons in related:
            template = tz_template_service.template_for_product(product.id)
            services.append({
                "product_id": product.id, "name": product.name, "summary": product.summary,
                "score": score, "reasons": reasons,
                "template_key": template.key, "template_name": template.name,
            })

    contractors = []
    seen_companies: set[str] = set()
    for result in search.products[:1]:
        for company in result.recommended_companies:
            if company.id in seen_companies:
                continue
            seen_companies.add(company.id)
            policy = _SUBCONTRACT_LABELS.get(company.subcontract_policy, company.subcontract_policy)
            contractors.append({
                "company_id": company.id,
                "name": company.name,
                "rating": company.rating,
                "service_name": result.product.name,
                "reasons": [
                    f"Выполняет услугу «{result.product.name}».",
                    company.description,
                    f"Рейтинг {company.rating:.1f}/5; {policy}.",
                ],
                "subcontract_policy": policy,
            })
            if len(contractors) >= 5:
                break
        if len(contractors) >= 5:
            break

    similar = []
    for overlap, _, item in historical[:4]:
        similar.append({
            "id": item["id"], "title": item["title"] or item["template_name"],
            "object_name": item.get("object_name") or "",
            "summary": item.get("goal") or f"Готовность {item.get('ready_score', 0)}%",
            "similarity": min(1.0, 0.45 + overlap * 0.12),
            "source": "Сохранённое ТЗ", "is_saved": True,
        })
    known_ids = {item["id"] for item in similar}
    for result in search.products[:1]:
        for case in result.similar_cases:
            if case.id in known_ids:
                continue
            known_ids.add(case.id)
            similar.append({
                "id": case.id, "title": case.title, "object_name": case.object_name,
                "summary": case.summary, "similarity": result.score,
                "source": "Исторический кейс", "is_saved": False,
            })
            if len(similar) >= 6:
                break
        if len(similar) >= 6:
            break

    document = enriched.get("current_document") or enriched.get("tz") or {}
    base_label = _INTENT_LABELS.get(search.detected_intent, str(search.detected_intent))
    intent_label = f"{base_label}: {top.product.name}" if top else base_label
    overlap_count = len(
        search_service._query_tokens(search.query) & search_service._product_terms(top.product)
    ) if top else 0
    intent_confidence = min(0.98, 0.55 + overlap_count * 0.07) if overlap_count else 0.35
    return {
        "intent": {
            "code": search.detected_intent,
            "label": intent_label,
            "confidence": intent_confidence,
        },
        "services": services,
        "contractors": contractors,
        "similar_tz": similar,
        "filling_recommendations": _filling_recommendations(document, product_id),
        "conditional_services": _conditional_services(search.query, document, product_id),
    }


async def enrich_assistant_context(message: str, context: dict | None) -> dict:
    """Дополняет контекст текущими данными каталога и сохранённых ТЗ."""
    enriched = dict(context or {})
    search = search_service.search(message, limit=3)
    recommendations = []
    for item in search.products:
        template = tz_template_service.template_for_product(item.product.id)
        recommendations.append({
            "template_key": template.key,
            "template_name": template.name,
            "product_id": item.product.id,
            "product_name": item.product.name,
            "score": item.score,
            "reasons": item.reasons,
        })

    documents = await tz_repository.list()
    query_tokens = _tokens(message)
    historical = []
    for document in documents:
        haystack = " ".join([
            document.title, document.template_name, document.object_name or "",
            document.input_data.goal or "",
            " ".join(section.content[:500] for section in document.sections),
        ])
        overlap = len(query_tokens & _tokens(haystack))
        if overlap or not query_tokens:
            historical.append((overlap, str(document.updated_at or document.created_at or ""), {
                "id": document.id,
                "title": document.title,
                "template_key": document.template_key,
                "template_name": document.template_name,
                "object_name": document.object_name,
                "goal": document.input_data.goal,
                "ready_score": document.ready_score,
                "matching_terms": overlap,
            }))
    historical.sort(key=lambda item: (item[0], item[1]), reverse=True)
    enriched["knowledge_base"] = {
        "recommended_templates": recommendations,
        "similar_created_tz": [item[2] for item in historical[:5]],
        "exceptional_conditions": collect_exceptional_conditions(documents, message),
        "created_tz_count": len(documents),
        "usage_rule": (
            "Исторические особые условия — только справочные. Не переносить их в текущее ТЗ, "
            "если они не подтверждены текущими полями или сообщениями пользователя."
        ),
    }
    enriched["discovery"] = _build_discovery(search, historical, enriched)
    return enriched
