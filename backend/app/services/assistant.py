from backend.app.schemas.assistant import AssistantChatRequest


class AssistantService:
    def reply(self, payload: AssistantChatRequest) -> str:
        message = payload.message.lower()
        context = payload.context or {}
        draft = context.get("draft") or {}
        product = context.get("selected_product") or {}

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

        return "Могу найти услугу, проверить риски или кратко собрать ТЗ."


assistant_service = AssistantService()
