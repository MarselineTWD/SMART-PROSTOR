from typing import Any

from pydantic import BaseModel, Field

from backend.app.models.domain import TZDocument, TZFieldUpdate


class AssistantMessage(BaseModel):
    role: str
    text: str


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    context: dict[str, Any] = Field(default_factory=dict)
    history: list[AssistantMessage] = Field(default_factory=list)


class DraftAssistantChatRequest(AssistantChatRequest):
    document: TZDocument


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


class AssistantIntent(BaseModel):
    code: str
    label: str
    confidence: float = 0.0


class AssistantServiceMatch(BaseModel):
    product_id: str
    name: str
    summary: str = ""
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    template_key: str | None = None
    template_name: str | None = None


class AssistantContractorMatch(BaseModel):
    company_id: str
    name: str
    rating: float | None = None
    service_name: str
    reasons: list[str] = Field(default_factory=list)
    subcontract_policy: str = ""


class AssistantSimilarTz(BaseModel):
    id: str
    title: str
    object_name: str = ""
    summary: str = ""
    similarity: float = 0.0
    source: str = "catalog"
    is_saved: bool = False


class AssistantFillRecommendation(BaseModel):
    field: str
    label: str
    recommendation: str
    priority: str = "medium"


class AssistantConditionalService(BaseModel):
    name: str
    status: str
    condition: str
    reason: str


class AssistantDiscovery(BaseModel):
    intent: AssistantIntent
    services: list[AssistantServiceMatch] = Field(default_factory=list)
    contractors: list[AssistantContractorMatch] = Field(default_factory=list)
    similar_tz: list[AssistantSimilarTz] = Field(default_factory=list)
    filling_recommendations: list[AssistantFillRecommendation] = Field(default_factory=list)
    conditional_services: list[AssistantConditionalService] = Field(default_factory=list)


class AssistantChatResponse(BaseModel):
    reply: str
    suggestions: list[str] = Field(default_factory=list)
    field_updates: list[TZFieldUpdate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider: str = "rules"
    model: str | None = None
    fallback: bool = False
    discovery: AssistantDiscovery | None = None


class AssistantStatusResponse(BaseModel):
    enabled: bool
    provider: str
    model: str
