from fastapi import APIRouter

from backend.app.schemas.assistant import AssistantChatRequest, AssistantChatResponse, DraftAssistantChatRequest
from backend.app.core.config import settings
from backend.app.schemas.assistant import AssistantStatusResponse
from backend.app.services.assistant import assistant_service
from backend.app.services.assistant_context import enrich_assistant_context
from backend.app.services.tz_chat import tz_chat_service
from backend.app.services.tz_templates import tz_template_service


router = APIRouter()


@router.post("/chat", response_model=AssistantChatResponse)
async def chat(payload: AssistantChatRequest) -> AssistantChatResponse:
    payload.context = await enrich_assistant_context(payload.message, payload.context)
    response = assistant_service.reply(payload)
    response.discovery = payload.context.get("discovery")
    return response


@router.post("/draft-chat", response_model=AssistantChatResponse)
async def draft_chat(payload: DraftAssistantChatRequest) -> AssistantChatResponse:
    template = tz_template_service.get_or_default(payload.document.template_key)
    context = await enrich_assistant_context(payload.message, payload.context)
    context["tz"] = payload.document.model_dump(mode="json")
    reply, provider, fallback = assistant_service.generate(
        message=payload.message,
        context=context,
        history=[(item.role, item.text) for item in payload.history],
        allowed_fields=tz_chat_service.allowed_fields(payload.document, template),
    )
    return AssistantChatResponse(
        reply=reply.reply,
        suggestions=reply.suggestions,
        field_updates=reply.field_updates,
        warnings=reply.warnings,
        provider=provider,
        model=settings.llm_model if provider == "deepseek" else None,
        fallback=fallback,
        discovery=context.get("discovery"),
    )


@router.get("/status", response_model=AssistantStatusResponse)
def status() -> AssistantStatusResponse:
    return AssistantStatusResponse(
        enabled=settings.llm_enabled,
        provider="deepseek" if settings.llm_enabled else "rules",
        model=settings.llm_model,
    )
