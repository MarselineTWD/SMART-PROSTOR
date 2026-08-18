"""Схема ответа «топ-3 подрядчика под ТЗ»."""
from __future__ import annotations

from pydantic import BaseModel

from backend.app.schemas.estimate import (
    AdditionalServiceCost,
    RoadmapStage,
    TeamMember,
)


class MatchedProductRef(BaseModel):
    id: str | None
    name: str | None


class ContractorPick(BaseModel):
    company_id: str
    company_name: str
    rating: float | None = None
    info: str = ""
    services: str = ""
    contract_number: str = ""
    calc_id: str
    calc_name: str = ""

    # Историческая база под срок
    estimated_days: int
    estimated_weeks: float
    estimated_months: float
    min_days: int
    max_days: int
    variants: int

    # Данные для диаграммы Ганта
    stage_count: int
    stages: list[RoadmapStage] = []

    # Полная стоимость в рублях
    workdays: int
    total_hours: int
    team: list[TeamMember] = []
    cost_without_vat: float
    vat_rate: float
    vat_amount: float
    cost_with_vat: float

    # Почему этот подрядчик — в шорт-листе
    recommendation_reason: str  # "fastest" | "cheapest" | "top_rated" | "value"

    # Не обязательные (совместимость)
    additional_services: list[AdditionalServiceCost] = []
    cost_basis: str = ""
    cost_confidence: str = "indicative"


class ContractorAnalysisResponse(BaseModel):
    tz_id: str | None
    tz_title: str | None = None
    matched_product: MatchedProductRef | None = None
    plan_start: str | None = None
    vat_rate: float
    cost_disclaimer: str
    contractors: list[ContractorPick] = []
