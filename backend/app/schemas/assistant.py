from typing import Any

from pydantic import BaseModel, Field


class AssistantMessage(BaseModel):
    role: str
    text: str


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    context: dict[str, Any] = Field(default_factory=dict)
    history: list[AssistantMessage] = Field(default_factory=list)


class AssistantChatResponse(BaseModel):
    reply: str
