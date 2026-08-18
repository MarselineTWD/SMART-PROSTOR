"""Схемы Pydantic для аналитики подрядчиков (`/api/analytics/contractors/*`)."""
from __future__ import annotations

from pydantic import BaseModel


class ContractorRankItem(BaseModel):
    company_id: str
    company_name: str
    rating: float | None = None
    value: float


class MarketShareItem(BaseModel):
    company_id: str
    company_name: str
    orders: int
    orders_share: float
    cost_without_vat: float
    cost_share: float
    days: int
    days_share: float


class ContractorProductStats(BaseModel):
    product_id: str
    product_name: str
    orders: int
    total_days: int
    total_cost_without_vat: float


class ContractorContractStats(BaseModel):
    contract_id: str
    number: str = ""
    orders: int
    total_days: int
    total_cost_without_vat: float


class LeaderboardSummary(BaseModel):
    total_contractors: int
    total_orders: int
    total_calendar_days: int
    total_cost_without_vat: float
    average_orders_per_contractor: float
    average_cost_per_contractor: float
    average_rating: float
    cost_disclaimer: str
    vat_rate: float


class ContractorLeaderboardResponse(BaseModel):
    summary: LeaderboardSummary
    top_by_orders: list[ContractorRankItem]
    top_by_cost_without_vat: list[ContractorRankItem]
    top_by_calendar_days: list[ContractorRankItem]
    top_by_rating: list[ContractorRankItem]
    top_by_avg_cost_per_order: list[ContractorRankItem]
    top_by_avg_days_per_order: list[ContractorRankItem]
    market_share: list[MarketShareItem]


class ContractorProfileResponse(BaseModel):
    company_id: str
    company_name: str
    rating: float | None = None
    info: str = ""
    services: str = ""

    order_count: int
    contract_count: int
    product_count: int
    stage_count: int

    avg_days_per_order: float
    min_days_per_order: int
    max_days_per_order: int
    total_calendar_days: int
    total_workdays: int

    total_cost_without_vat: float
    total_cost_with_vat: float
    avg_cost_per_order: float
    max_concurrent_orders: int

    products: list[ContractorProductStats] = []
    contracts: list[ContractorContractStats] = []


class MonthlyLoadPoint(BaseModel):
    month: str  # YYYY-MM
    active_orders: int


class WorkloadOrderItem(BaseModel):
    calc_id: str
    product_id: str
    product_name: str
    name: str = ""
    start_date: str
    end_date: str
    days: int


class ContractorWorkloadResponse(BaseModel):
    company_id: str
    company_name: str
    total_orders_with_dates: int
    monthly_load: list[MonthlyLoadPoint]
    orders: list[WorkloadOrderItem]


class ProductForContractor(BaseModel):
    product_id: str
    product_name: str
    orders: int


class ContractorMatrixRow(BaseModel):
    company_id: str
    company_name: str
    rating: float | None = None
    product_count: int
    products: list[ProductForContractor]


class ProductCoverageItem(BaseModel):
    product_id: str
    product_name: str
    contractor_count: int
    order_count: int


class ContractorProductMatrixResponse(BaseModel):
    contractors: list[ContractorMatrixRow]
    product_coverage: list[ProductCoverageItem]
