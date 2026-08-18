from pydantic import BaseModel


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


class EstimateSummary(BaseModel):
    company_count: int
    fastest_days: int
    slowest_days: int
    average_days: int
    fastest_company: str


class ProductEstimateResponse(BaseModel):
    product_id: str
    product_name: str
    operations: list[str] = []
    roles: list[str] = []
    companies: list[ContractorEstimate] = []
    summary: EstimateSummary


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
