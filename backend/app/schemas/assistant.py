from typing import Any

from pydantic import BaseModel, Field

from backend.app.models.domain import TZFieldUpdate


class AssistantMessage(BaseModel):
    role: str
    text: str


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    context: dict[str, Any] = Field(default_factory=dict)
    history: list[AssistantMessage] = Field(default_factory=list)


class AllowedField(BaseModel):
    """Описание поля ТЗ, которое ИИ разрешено заполнять (белый список)."""

    target: str
    key: str
    label: str
    type: str = "text"


class AssistantReply(BaseModel):
    """Строгий контракт ответа модели: только эти ключи, без markdown и мусора."""

    reply: str = ""
    suggestions: list[str] = Field(default_factory=list)
    field_updates: list[TZFieldUpdate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AssistantChatResponse(BaseModel):
    reply: str
    suggestions: list[str] = Field(default_factory=list)
    field_updates: list[TZFieldUpdate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider: str = "rules"
    model: str | None = None
    fallback: bool = False


class AssistantStatusResponse(BaseModel):
    enabled: bool
    provider: str
    model: str
