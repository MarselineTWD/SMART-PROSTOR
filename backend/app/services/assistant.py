from backend.app.schemas.assistant import AssistantChatRequest


import json

from backend.app.core.config import settings
from backend.app.schemas.assistant import AssistantChatResponse
from backend.app.services.llm import llm_complete


class AssistantService:
    def reply(self, payload: AssistantChatRequest) -> AssistantChatResponse:
        llm_reply = self._llm_reply(payload)
        if llm_reply:
            return AssistantChatResponse(
                reply=llm_reply, provider="deepseek", model=settings.llm_model, fallback=False
            )
        return AssistantChatResponse(
            reply=self._fallback_reply(payload), provider="rules", model=None,
            fallback=settings.llm_enabled,
        )

    def _llm_reply(self, payload: AssistantChatRequest) -> str | None:
        history = "\n".join(f"{item.role}: {item.text}" for item in payload.history[-8:])
        context = json.dumps(payload.context or {}, ensure_ascii=False, default=str)
        system = (
            "Ты — помощник конструктора технических заданий ПРОСТОР для нефтегазовых работ. "
            "Отвечай на русском кратко и конкретно. Опирайся только на переданный контекст. "
            "Не придумывай договорные ставки, факты и результаты проверок. "
            "Если есть validation_issues, сначала объясни критичные замечания и предложи исправления. "
            "Денежные оценки называй индикативными, если договорные ставки отсутствуют."
        )
        prompt = f"Контекст:\n{context}\nИстория:\n{history}\nЗапрос пользователя:\n{payload.message}"
        return llm_complete(system, prompt, temperature=0.2)

    def _fallback_reply(self, payload: AssistantChatRequest) -> str:
        message = payload.message.lower()
        context = payload.context or {}
        draft = context.get("draft") or {}
        product = context.get("selected_product") or {}
        tz = context.get("tz") or {}

        if ("дополн" in message or "заполн" in message) and ("тз" in message or "раздел" in message or tz or draft):
            return (
                "Дополню пустые разделы ТЗ по текущим данным. "
                "Нажмите «Дополнить с ИИ» — заполню недостающие разделы, уже заполненные не трону."
            )

        if "сгенерир" in message or "полностью" in message or "сделай тз" in message or "напиши тз" in message:
            return (
                "Соберу ТЗ целиком по выбранному шаблону и введённым данным. "
                "Нажмите «Сгенерировать полностью» — перезапишу все разделы связным текстом."
            )

        if "шаблон" in message or "переключ" in message:
            return (
                "Можно переключить шаблон ТЗ в конструкторе: доступны ПТД, ОПЗ, концепты "
                "геологии/обустройства/развития/заканчивания, сопровождение и универсальная форма."
            )

        if "уточ" in message or "вопрос" in message:
            return "Уточните объект, цель, срок, исходные данные и субподряд."

        if "провер" in message or "риск" in message or "готов" in message:
            if not draft:
                return "Черновик ещё не создан."
            risks = draft.get("risks") or []
            score = draft.get("ready_score", 0)
            if not risks:
                return f"Готовность {score}%. Критичных рисков нет."
            risk_text = "; ".join((risk.get("message") or str(risk)) for risk in risks[:3])
            return f"Готовность {score}%. Риски: {risk_text}."

        if "крат" in message or "резюме" in message or "собери" in message:
            if draft:
                return f"{draft.get('product_name')}. Исполнитель: {draft.get('company_name') or 'не выбран'}. Готовность: {draft.get('ready_score', 0)}%."
            if product:
                return f"{product.get('name')}. {product.get('summary')}"
            return "Сначала выберите продукт."

        if "сформ" in message or "тз" in message:
            if product:
                return "Нажмите «Сформировать ТЗ»."
            return "Сначала выберите продукт."

        return "Могу найти услугу, проверить риски, дополнить или полностью сгенерировать ТЗ."


assistant_service = AssistantService()
