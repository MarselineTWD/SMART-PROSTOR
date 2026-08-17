from pydantic import BaseModel


class AnalyticsOverview(BaseModel):
    total_products: int
    total_companies: int
    total_active_contracts: int
    total_historical_cases: int
    dataset_coverage: dict[str, int]
    most_requested_products: list[str]
    popular_work_types: list[str]
    common_stages: list[str]
    common_risk_patterns: list[str]
    typical_request_errors: list[str]
    product_packaging_candidates: list[str]
    popular_service_combinations: list[str]
    contractors_with_analogs: list[str]
    empty_field_patterns: list[str]
    unrecognized_query_patterns: list[str]
