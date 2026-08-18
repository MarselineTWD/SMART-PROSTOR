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
    "- reply: строка на русском, максимум 3 коротких предложения, деловой тон, "
    "без markdown, эмодзи, маркированных списков и лишних символов.\n"
    "- suggestions: до 4 коротких подсказок-действий (массив строк).\n"
    "- field_updates: массив значений, извлечённых из диалога для заполнения ТЗ. "
    'Каждый элемент — объект {"target", "key", "value", "confidence", "evidence"}. '
    "target и key бери ТОЛЬКО из списка разрешённых полей. value — итоговое значение "
    "(для флагов true/false, для процента — число). confidence — число 0..1. "
    "evidence — короткая цитата из сообщения пользователя.\n"
    "- warnings: массив строк с предупреждениями (недостающие данные, критичные "
    "замечания из validation_issues).\n"
    "ПРАВИЛА: опирайся только на переданный контекст и диалог; не выдумывай договорные "
    "ставки, сроки, факты и результаты проверок; денежные оценки называй индикативными; "
    "если данных не хватает — задай уточняющий вопрос в reply и не заполняй это поле."
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
        return self._fallback(message, context), "rules", settings.llm_enabled

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
            data = llm_complete_json(system, prompt, temperature=0.2)
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
        return kept[:12]

    # --- Детерминированный fallback (без сети) --------------------------------

    def _fallback(self, message: str, context: dict) -> AssistantReply:
        text = message.lower()
        draft = context.get("draft") or {}
        product = context.get("selected_product") or {}
        tz = context.get("tz") or {}
        suggestions = ["Что уточнить для ТЗ?", "Проверь готовность", "Дополнить ИИ"]

        if ("дополн" in text or "заполн" in text) and ("тз" in text or "раздел" in text or tz or draft):
            reply = (
                "Дополню пустые разделы ТЗ по текущим данным. Нажмите «Дополнить с ИИ» — "
                "заполню недостающие разделы, уже заполненные не трону."
            )
        elif "сгенерир" in text or "полност" in text or "сделай тз" in text or "напиши тз" in text:
            reply = (
                "Соберу ТЗ целиком по выбранному шаблону и введённым данным. "
                "Нажмите «Сгенерировать полностью» — перезапишу все разделы связным текстом."
            )
        elif "шаблон" in text or "переключ" in text:
            reply = (
                "Шаблон ТЗ можно переключить в конструкторе: доступны ПТД, ОПЗ, концепты "
                "геологии/обустройства/развития/заканчивания, сопровождение и универсальная форма."
            )
        elif "уточ" in text or "вопрос" in text:
            reply = "Уточните объект, цель, срок, исходные данные и субподряд."
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
        elif "сформ" in text or "тз" in text:
            reply = "Нажмите «Сформировать ТЗ»." if product else "Сначала выберите продукт."
        else:
            reply = "Могу найти услугу, проверить готовность, дополнить или полностью сгенерировать ТЗ."

        return AssistantReply(reply=reply, suggestions=suggestions)


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
