from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


IntentType = Literal[
    "service_search",
    "contractor_selection",
    "similar_cases",
    "draft_generation",
]


class Company(BaseModel):
    id: str
    name: str
    description: str
    rating: float = Field(ge=0, le=5)
    product_ids: list[str] = Field(default_factory=list)
    subcontract_policy: Literal["allowed", "limit_70", "forbidden", "separate_rs_required"] = "allowed"


class Contract(BaseModel):
    id: str
    company_id: str
    name: str
    is_active: bool = True
    product_ids: list[str] = Field(default_factory=list)


class Product(BaseModel):
    id: str
    name: str
    summary: str
    keywords: list[str] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=list)
    active_contract_ids: list[str] = Field(default_factory=list)
    template_id: str
    has_price_rules: bool = True
    has_operations: bool = True
    is_legacy: bool = False
    synonyms: list[str] = Field(default_factory=list)


class HistoricalCase(BaseModel):
    id: str
    product_id: str
    title: str
    summary: str
    company_id: str
    object_name: str


class TemplateField(BaseModel):
    key: str
    label: str
    required: bool = True


class TemplateSection(BaseModel):
    key: str
    title: str
    required_fields: list[TemplateField] = Field(default_factory=list)


class Template(BaseModel):
    id: str
    product_id: str
    name: str
    sections: list[TemplateSection] = Field(default_factory=list)
    stage_presets: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    product: Product
    score: float = Field(ge=0)
    reasons: list[str] = Field(default_factory=list)
    recommended_companies: list[Company] = Field(default_factory=list)
    similar_cases: list[HistoricalCase] = Field(default_factory=list)


class SearchContext(BaseModel):
    query: str
    detected_intent: IntentType
    products: list[SearchResult] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class DraftInputData(BaseModel):
    object_name: str | None = None
    customer_name: str | None = None
    goal: str | None = None
    deadline: str | None = None
    source_data_ready: bool = False
    needs_3d_model: bool = False
    requires_subcontractor: bool = False
    subcontract_share_percent: int | None = Field(default=None, ge=0, le=100)
    separate_subcontract_estimate: bool = False


class DraftDocument(BaseModel):
    kind: Literal["tz", "calendar_plan", "cost_estimate"]
    status: Literal["planned", "ready"]


class DraftRisk(BaseModel):
    code: str
    severity: Literal["low", "medium", "high"]
    message: str
    recommendation: str


class RequestDraft(BaseModel):
    id: str
    product_id: str
    product_name: str
    template_id: str
    company_id: str | None = None
    company_name: str | None = None
    contract_id: str | None = None
    contract_name: str | None = None
    stages: list[str] = Field(default_factory=list)
    required_fields: list[TemplateField] = Field(default_factory=list)
    input_data: DraftInputData = Field(default_factory=DraftInputData)
    risks: list[DraftRisk] = Field(default_factory=list)
    ready_score: int = Field(default=0, ge=0, le=100)
    documents: list[DraftDocument] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# --- Шаблоны и документы ТЗ ---------------------------------------------------

SectionSource = Literal["template", "manual", "ai"]
TZStatus = Literal["draft", "ready", "archived"]


class TZField(BaseModel):
    key: str
    label: str
    placeholder: str = ""
    required: bool = False
    input_type: Literal["text", "date", "number", "select", "checkbox", "textarea"] = "text"
    options: list[str] = Field(default_factory=list)
    group: str = "Основные данные"


class TZTemplateSection(BaseModel):
    key: str
    title: str
    hint: str = ""
    ai_fillable: bool = True


class TZTemplate(BaseModel):
    key: str
    name: str
    product_id: str | None = None
    description: str = ""
    stage_presets: list[str] = Field(default_factory=list)
    fields: list[TZField] = Field(default_factory=list)
    sections: list[TZTemplateSection] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)
    example: dict[str, Any] = Field(default_factory=dict)


class TZDocumentSection(BaseModel):
    key: str
    title: str
    content: str = ""
    source: SectionSource = "template"


class TZDocument(BaseModel):
    id: str
    template_key: str
    template_name: str = ""
    product_id: str | None = None
    title: str = ""
    object_name: str | None = None
    customer_name: str | None = None
    executor_name: str | None = None
    contract_name: str | None = None
    status: TZStatus = "draft"
    ready_score: int = Field(default=0, ge=0, le=100)
    requisites: dict[str, Any] = Field(default_factory=dict)
    input_data: DraftInputData = Field(default_factory=DraftInputData)
    sections: list[TZDocumentSection] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

