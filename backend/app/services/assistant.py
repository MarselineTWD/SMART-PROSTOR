"""AI-ассистент по ТЗ: структурированный ответ, санитайзинг и белый список правок.

Модель обязана вернуть строгий JSON по контракту :class:`AssistantReply`.
Ответ очищается от markdown/мусора, а извлечённые правки (``field_updates``)
фильтруются по белому списку разрешённых полей. При любой ошибке LLM —
детерминированный fallback на правилах.
"""
from __future__ import annotations

import json
import re

from backend.app.core.config import settings
from backend.app.models.domain import TZFieldUpdate
from backend.app.schemas.assistant import (
    AllowedField,
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantReply,
)
from backend.app.services.llm import llm_complete_json


_MD_NOISE = re.compile(r"[*_`#>|~]+")
_BULLET = re.compile(r"^\s*(?:[-•*]+|\d+[.)])\s+")

_SYSTEM = (
    "Ты — ассистент-конструктор технических заданий ПРОСТОР для нефтегазовых работ.\n"
    "ФОРМАТ ОТВЕТА: верни СТРОГО один JSON-объект с ключами "
    '"reply", "suggestions", "field_updates", "warnings". Никакого текста вне JSON.\n'
    "- reply: строка на русском, максимум 2 коротких предложения, деловой тон, "
    "без markdown, эмодзи, маркированных списков и лишних символов.\n"
    "- suggestions: до 4 коротких подсказок-действий (массив строк).\n"
    "- field_updates: массив значений, извлечённых из диалога для заполнения ТЗ. "
    'Каждый элемент — объект {"target", "key", "value", "confidence", "evidence"}. '
    "target и key бери ТОЛЬКО из списка разрешённых полей. value — итоговое значение "
    "(для флагов true/false, для процента — число, для поля типа services — массив "
    "объектов с ключом name). confidence — число 0..1. "
    "evidence — короткая цитата из сообщения пользователя.\n"
    "- warnings: массив строк с предупреждениями (недостающие данные, критичные "
    "замечания из validation_issues).\n"
    "ПРАВИЛА РАБОТЫ: весь объект tz/current_document в контексте — это актуальные поля "
    "конструктора; обязательно учитывай каждое заполненное поле и не спрашивай его повторно. "
    "История диалога равноправна полям конструктора. Из каждого сообщения сразу извлекай "
    "все возможные field_updates — интерфейс применит их автоматически. Если пользователь "
    "просит собрать, создать, сформировать или заполнить ТЗ, не отправляй его к кнопкам: "
    "верни максимум доступных правок по всему контексту, а разделы сформирует интерфейс. "
    "Не устраивай анкетирование: допускается не более ОДНОГО короткого вопроса и только если "
    "без ответа нельзя безопасно продолжить. Некритичные пробелы оставляй как предупреждения. "
    "Заказчик, исполнитель и номер договора никогда не блокируют заполнение черновика: не "
    "спрашивай их, если пользователь сам не обсуждает эти реквизиты. Если уже нашёл хотя бы "
    "одно значение для field_updates, в reply сообщи о действии без вопроса. "
    "Особые условия из knowledge_base.exceptional_conditions используй только для сверки и "
    "предупреждения о совпадении/конфликте, не копируй без подтверждения пользователя. "
    "Не выдумывай договорные ставки, сроки и факты; денежные оценки называй индикативными."
)


class AssistantService:
    # --- Публичные методы ----------------------------------------------------

    def reply(self, payload: AssistantChatRequest) -> AssistantChatResponse:
        """Ответ для stateless-чата (без привязки к документу): без правок полей."""
        reply, provider, fallback = self.generate(
            message=payload.message,
            context=payload.context or {},
            history=[(m.role, m.text) for m in payload.history],
            allowed_fields=None,
        )
        return AssistantChatResponse(
            reply=reply.reply,
            suggestions=reply.suggestions,
            field_updates=reply.field_updates,
            warnings=reply.warnings,
            provider=provider,
            model=settings.llm_model if provider == "deepseek" else None,
            fallback=fallback,
        )

    def generate(
        self,
        *,
        message: str,
        context: dict,
        history: list[tuple[str, str]],
        allowed_fields: list[AllowedField] | None,
    ) -> tuple[AssistantReply, str, bool]:
        """Возвращает (очищенный ответ, провайдер, флаг fallback)."""
        if settings.llm_enabled:
            parsed = self._llm_structured(message, context, history, allowed_fields)
            if parsed is not None:
                return self._postprocess(parsed, allowed_fields), "deepseek", False
        fallback_reply = self._fallback(message, context, allowed_fields, history)
        return self._postprocess(fallback_reply, allowed_fields), "rules", settings.llm_enabled

    # --- LLM с валидацией и одним повтором ------------------------------------

    def _llm_structured(
        self,
        message: str,
        context: dict,
        history: list[tuple[str, str]],
        allowed_fields: list[AllowedField] | None,
    ) -> AssistantReply | None:
        prompt = self._build_prompt(message, context, history, allowed_fields)
        for attempt in range(2):
            system = _SYSTEM if attempt == 0 else _SYSTEM + (
                "\nПРЕДЫДУЩИЙ ОТВЕТ БЫЛ НЕВАЛИДНЫМ. Верни только корректный JSON-объект "
                "с указанными ключами."
            )
            data = llm_complete_json(system, prompt, temperature=0.15, max_tokens=1800)
            if data is None:
                return None
            try:
                return AssistantReply.model_validate(data)
            except Exception:  # noqa: BLE001 — невалидный ответ -> повтор/fallback
                continue
        return None

    def _build_prompt(
        self,
        message: str,
        context: dict,
        history: list[tuple[str, str]],
        allowed_fields: list[AllowedField] | None,
    ) -> str:
        ctx = json.dumps(context or {}, ensure_ascii=False, default=str)
        convo = "\n".join(f"{role}: {text}" for role, text in history[-8:]) or "—"
        if allowed_fields:
            fields = "\n".join(
                f"- target={f.target} key={f.key} ({f.label}) тип={f.type}"
                for f in allowed_fields
            )
        else:
            fields = "нет — не заполняй field_updates, оставь пустой массив."
        return (
            f"Контекст:\n{ctx}\n\n"
            f"Разрешённые поля для field_updates:\n{fields}\n\n"
            f"История диалога:\n{convo}\n\n"
            f"Запрос пользователя:\n{message}"
        )

    # --- Постобработка: очистка + белый список --------------------------------

    def _postprocess(
        self, reply: AssistantReply, allowed_fields: list[AllowedField] | None
    ) -> AssistantReply:
        reply.reply = sanitize_text(reply.reply, limit=1500)
        reply.suggestions = _clean_list(reply.suggestions, limit=4, item_limit=80)
        reply.warnings = _clean_list(reply.warnings, limit=6, item_limit=200)
        reply.field_updates = self._whitelist(reply.field_updates, allowed_fields)
        if reply.field_updates:
            reply.reply = re.sub(
                r"(?:уточните|укажите|сообщите|подскажите)[^.?!]*(?:[.?!]|$)",
                "Недостающие некритичные реквизиты отмечены в предупреждениях.",
                reply.reply,
                flags=re.IGNORECASE,
            ).strip()
        if not reply.reply and reply.field_updates:
            reply.reply = "Предлагаю заполнить поля ТЗ значениями из диалога — проверьте и примените."
        return reply

    def _whitelist(
        self, updates: list[TZFieldUpdate], allowed_fields: list[AllowedField] | None
    ) -> list[TZFieldUpdate]:
        if not allowed_fields:
            return []
        index = {(a.target, a.key): a for a in allowed_fields}
        kept: list[TZFieldUpdate] = []
        for u in updates:
            allowed = index.get((u.target, u.key))
            if allowed is None:
                continue
            if u.value is None or (isinstance(u.value, str) and not u.value.strip()):
                continue
            if isinstance(u.value, str):
                u.value = sanitize_text(u.value, limit=4000)
            u.label = allowed.label
            u.evidence = sanitize_text(u.evidence, limit=200)
            u.confidence = max(0.0, min(1.0, float(u.confidence or 0.0)))
            u.applied = False
            kept.append(u)
        return kept[:40]

    # --- Детерминированный fallback (без сети) --------------------------------

    def _fallback(
        self,
        message: str,
        context: dict,
        allowed_fields: list[AllowedField] | None = None,
        history: list[tuple[str, str]] | None = None,
    ) -> AssistantReply:
        text = message.lower()
        user_history = [item for role, item in (history or []) if role == "user"]
        conversation = "\n".join([*user_history[-8:], message])
        draft = context.get("draft") or {}
        product = context.get("selected_product") or {}
        tz = context.get("tz") or {}
        knowledge = context.get("knowledge_base") or {}
        recommended = knowledge.get("recommended_templates") or []
        similar = knowledge.get("similar_created_tz") or []
        suggestions = ["Подбери тип ТЗ", "Найди похожие ТЗ", "Что ещё заполнить?"]
        updates: list[TZFieldUpdate] = []

        allowed = {(field.target, field.key): field for field in (allowed_fields or [])}
        date_match = re.search(r"\b(20\d{2})[-./](\d{1,2})[-./](\d{1,2})\b", conversation)
        if date_match and ("input_data", "deadline") in allowed:
            year, month, day = date_match.groups()
            updates.append(TZFieldUpdate(
                target="input_data", key="deadline",
                value=f"{year}-{int(month):02d}-{int(day):02d}", confidence=0.95,
                evidence=date_match.group(0),
            ))
        object_match = re.search(
            r"(?:объект|месторождение|скважина|участок)\s*[:—-]?\s*([^,.\n]{3,80})",
            conversation,
            flags=re.IGNORECASE,
        )
        if object_match and ("document", "object_name") in allowed:
            updates.append(TZFieldUpdate(
                target="document", key="object_name", value=object_match.group(1).strip(),
                confidence=0.82, evidence=object_match.group(0),
            ))
        city_match = re.search(
            r"(?:место работ|локация|город|регион)\s*[:—-]?\s*([^,.\n]{2,80})",
            conversation,
            flags=re.IGNORECASE,
        )
        if city_match and ("requisites", "city") in allowed:
            updates.append(TZFieldUpdate(
                target="requisites", key="city", value=city_match.group(1).strip(),
                confidence=0.86, evidence=city_match.group(0),
            ))
        if any(word in text for word in ("нужно", "цель", "требуется", "подготовить")) \
                and ("input_data", "goal") in allowed:
            updates.append(TZFieldUpdate(
                target="input_data", key="goal", value=message.strip(),
                confidence=0.72, evidence=message[:180],
            ))
        if "3d" in text and ("input_data", "needs_3d_model") in allowed:
            updates.append(TZFieldUpdate(
                target="input_data", key="needs_3d_model", value=True,
                confidence=0.9, evidence="3D",
            ))
        if "субподряд" in text and ("input_data", "requires_subcontractor") in allowed:
            denied = any(phrase in text for phrase in ("не разреш", "запрет", "без субподряд", "не нужен", "не требуется"))
            updates.append(TZFieldUpdate(
                target="input_data", key="requires_subcontractor", value=not denied,
                confidence=0.88, evidence="субподряд",
            ))

        if ("дополн" in text or "заполн" in text) and ("тз" in text or "раздел" in text or tz or draft):
            reply = "Переношу данные диалога в поля и дополняю пустые разделы текущего ТЗ."
        elif "сгенерир" in text or "полност" in text or "сделай тз" in text or "напиши тз" in text:
            reply = "Собираю ТЗ целиком по полям и всей истории диалога."
        elif "шаблон" in text or "переключ" in text:
            reply = (
                "Шаблон ТЗ можно переключить в конструкторе: доступны ПТД, ОПЗ, концепты "
                "геологии/обустройства/развития/заканчивания, сопровождение и универсальная форма."
            )
        elif "уточ" in text or "вопрос" in text:
            missing = []
            if not (tz.get("object_name") or draft.get("object_name")):
                missing.append("объект")
            input_data = tz.get("input_data") or draft.get("input_data") or {}
            if not input_data.get("goal"):
                missing.append("цель")
            reply = f"Для продолжения достаточно уточнить: {', '.join(missing[:2])}." if missing else "Критичных уточнений нет — могу собирать ТЗ."
        elif "провер" in text or "риск" in text or "готов" in text:
            if not tz and not draft:
                reply = "ТЗ ещё не создано."
            else:
                score = tz.get("ready_score") if tz else draft.get("ready_score", 0)
                risks = draft.get("risks") or []
                if not risks:
                    reply = f"Готовность {score}%. Критичных замечаний нет."
                else:
                    risk_text = "; ".join((r.get("message") or str(r)) for r in risks[:3])
                    reply = f"Готовность {score}%. Замечания: {risk_text}."
        elif "крат" in text or "резюме" in text or "собери" in text:
            if draft:
                reply = (
                    f"{draft.get('product_name')}. Исполнитель: "
                    f"{draft.get('company_name') or 'не выбран'}. Готовность: "
                    f"{draft.get('ready_score', 0)}%."
                )
            elif product:
                reply = f"{product.get('name')}. {product.get('summary')}"
            else:
                reply = "Сначала выберите продукт."
        elif any(word in text for word in ("подбери", "тип тз", "похож", "аналог")):
            if recommended:
                first = recommended[0]
                similar_note = f" Нашёл {len(similar)} похожих ранее созданных ТЗ." if similar else ""
                reply = (
                    f"По каталогу лучше всего подходит «{first['template_name']}»."
                    f"{similar_note} Проверьте предложенные значения и тип ТЗ в конструкторе."
                )
            else:
                reply = "В базе нет уверенного совпадения. Уточните объект, результат и состав работ."
        elif "сформ" in text or "тз" in text:
            reply = "Заполните единый конструктор; ТЗ будет создано один раз финальной кнопкой."
        else:
            history_note = f" В базе учтено ранее созданных ТЗ: {knowledge.get('created_tz_count', 0)}."
            reply = "Могу подобрать тип по базе, заполнить поля, проверить готовность и рассчитать подрядчиков." + history_note

        return AssistantReply(reply=reply, suggestions=suggestions, field_updates=updates)


# --- Утилиты очистки текста ---------------------------------------------------

def sanitize_text(text: object, *, limit: int = 1500) -> str:
    """Убирает markdown/эмодзи-мусор, схлопывает пробелы и переносы, режет длину."""
    if not text:
        return ""
    value = _MD_NOISE.sub("", str(text))
    lines = []
    for line in value.splitlines():
        line = _BULLET.sub("", line)
        line = re.sub(r"[ \t]{2,}", " ", line).strip()
        lines.append(line)
    value = "\n".join(lines)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()[:limit]


def _clean_list(items: list[str], *, limit: int, item_limit: int) -> list[str]:
    result: list[str] = []
    for item in items or []:
        cleaned = sanitize_text(item, limit=item_limit)
        if cleaned and cleaned not in result:
            result.append(cleaned)
        if len(result) >= limit:
            break
    return result


assistant_service = AssistantService()
