from fastapi import APIRouter

from backend.app.schemas.assistant import AssistantChatRequest, AssistantChatResponse
from backend.app.services.assistant import assistant_service


router = APIRouter()


@router.post("/chat", response_model=AssistantChatResponse)
def chat(payload: AssistantChatRequest) -> AssistantChatResponse:
    return AssistantChatResponse(reply=assistant_service.reply(payload))
