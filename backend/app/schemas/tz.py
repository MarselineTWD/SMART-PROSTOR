from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.app.models.domain import (
    DraftInputData,
    TZDocument,
    TZDocumentSection,
    TZTemplate,
)


# --- Шаблоны ------------------------------------------------------------------

class TZTemplateSummary(BaseModel):
    key: str
    name: str
    product_id: str | None = None
    description: str = ""
    section_count: int = 0
    source_files: list[str] = Field(default_factory=list)


class TemplatesResponse(BaseModel):
    templates: list[TZTemplateSummary]


class TemplateDetailResponse(BaseModel):
    template: TZTemplate


# --- Документы ТЗ -------------------------------------------------------------

class TZCreateRequest(BaseModel):
    template_key: str
    product_id: str | None = None
    title: str | None = None
    object_name: str | None = None
    customer_name: str | None = None
    executor_name: str | None = None
    contract_name: str | None = None
    input_data: DraftInputData = Field(default_factory=DraftInputData)
    requisites: dict[str, Any] = Field(default_factory=dict)
    auto_fill: bool = False


class TZUpdateRequest(BaseModel):
    title: str | None = None
    object_name: str | None = None
    customer_name: str | None = None
    executor_name: str | None = None
    contract_name: str | None = None
    status: Literal["draft", "ready", "archived"] | None = None
    input_data: DraftInputData | None = None
    requisites: dict[str, Any] | None = None
    sections: list[TZDocumentSection] | None = None


class TZGenerateRequest(BaseModel):
    mode: Literal["augment", "full"] = "augment"
    instruction: str | None = None
    section_keys: list[str] | None = None


class TZSwitchTemplateRequest(BaseModel):
    template_key: str


class TZValidationIssue(BaseModel):
    code: str
    severity: Literal["high", "medium", "low"]
    title: str
    message: str
    recommendation: str
    field: str | None = None
    section_key: str | None = None


class TZValidationResult(BaseModel):
    valid: bool
    ready_score: int = Field(ge=0, le=100)
    filled_sections: int = 0
    total_sections: int = 0
    issue_counts: dict[str, int] = Field(default_factory=dict)
    issues: list[TZValidationIssue] = Field(default_factory=list)


class TZDocumentResponse(BaseModel):
    document: TZDocument
    validation: TZValidationResult


class TZDocumentSummary(BaseModel):
    id: str
    template_key: str
    template_name: str = ""
    title: str = ""
    object_name: str | None = None
    customer_name: str | None = None
    status: str = "draft"
    ready_score: int = 0
    updated_at: str | None = None


class TZListResponse(BaseModel):
    documents: list[TZDocumentSummary]
