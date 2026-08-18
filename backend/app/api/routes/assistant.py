from fastapi import APIRouter

from backend.app.schemas.assistant import AssistantChatRequest, AssistantChatResponse
from backend.app.core.config import settings
from backend.app.schemas.assistant import AssistantStatusResponse
from backend.app.services.assistant import assistant_service


router = APIRouter()


@router.post("/chat", response_model=AssistantChatResponse)
def chat(payload: AssistantChatRequest) -> AssistantChatResponse:
    return assistant_service.reply(payload)


@router.get("/status", response_model=AssistantStatusResponse)
def status() -> AssistantStatusResponse:
    return AssistantStatusResponse(
        enabled=settings.llm_enabled,
        provider="deepseek" if settings.llm_enabled else "rules",
        model=settings.llm_model,
    )
