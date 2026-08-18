from pydantic import BaseModel


class AdditionalServiceOption(BaseModel):
    product_id: str
    name: str
    common_company_count: int
    role_count: int
    operation_count: int
    min_cost_without_vat: float


class AdditionalServiceCost(BaseModel):
    product_id: str
    name: str
    estimated_days: int
    cost_without_vat: float


class RoadmapStage(BaseModel):
    order: int
    name: str
    days: int
    weeks: float
    offset_days: int
    percent: float
    documentation: str = ""
    start_date: str | None = None
    end_date: str | None = None
    estimated_cost_without_vat: float = 0
    # Сезонные ограничения (какие работы можно вести только в определённые месяцы).
    allowed_months: list[int] = []          # 1–12; пусто = без ограничений (круглогодично)
    constraint_season: str = ""             # "", "winter", "summer"
    constraint_label: str = ""              # человекочитаемая метка окна работ
    constraint_reason: str = ""             # почему есть ограничение
    gap_days: int = 0                       # простой перед этапом в ожидании допустимого сезона


class ContractorEstimate(BaseModel):
    company_id: str
    company_name: str
    rating: float | None = None
    info: str = ""
    services: str = ""
    contract_number: str = ""
    calc_id: str
    calc_name: str = ""
    estimated_days: int
    estimated_weeks: float
    estimated_months: float
    min_days: int
    max_days: int
    variants: int
    stage_count: int
    stages: list[RoadmapStage] = []
    # Календарный план с учётом сезонных ограничений (для диаграммы Ганта).
    plan_start: str | None = None
    plan_end: str | None = None
    calendar_days: int = 0                  # длительность плана по календарю (с простоями)
    season_wait_days: int = 0               # суммарный простой из-за сезонных окон
    workdays: int
    role_count: int
    average_fte: float
    base_day_rate_rub: float
    cost_without_vat: float
    vat_rate: float
    vat_amount: float
    cost_with_vat: float
    cost_basis: str
    cost_confidence: str = "indicative"
    base_cost_without_vat: float
    additional_cost_without_vat: float = 0
    additional_services: list[AdditionalServiceCost] = []


class EstimateSummary(BaseModel):
    company_count: int
    fastest_days: int
    slowest_days: int
    average_days: int
    fastest_company: str
    lowest_cost_without_vat: float
    highest_cost_without_vat: float
    average_cost_without_vat: float
    lowest_cost_company: str
    vat_rate: float
    cost_disclaimer: str


class ProductEstimateResponse(BaseModel):
    product_id: str
    product_name: str
    operations: list[str] = []
    roles: list[str] = []
    companies: list[ContractorEstimate] = []
    summary: EstimateSummary
    available_additional_services: list[AdditionalServiceOption] = []
    selected_additional_product_ids: list[str] = []
    roadmap_source: str = "catalog"
    tz_id: str | None = None
    tz_title: str | None = None


class ProductSummary(BaseModel):
    product_id: str
    name: str
    company_count: int
    calc_count: int
    operation_count: int
    min_days: int
    max_days: int


class ProductsResponse(BaseModel):
    products: list[ProductSummary] = []


class ProductMatch(BaseModel):
    product_id: str
    name: str
    score: float
    overlap: int


class MatchResponse(BaseModel):
    matches: list[ProductMatch] = []


class TZEstimateResponse(BaseModel):
    query: str
    matched: ProductMatch | None = None
    alternatives: list[ProductMatch] = []
    estimate: ProductEstimateResponse | None = None
