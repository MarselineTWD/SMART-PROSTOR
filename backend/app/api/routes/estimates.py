from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.estimate import (
    MatchResponse,
    ProductEstimateResponse,
    ProductsResponse,
    TZEstimateResponse,
)
from backend.app.services.procurement import procurement_service
from backend.app.services.tz_repository import tz_repository


router = APIRouter()


@router.get("/products", response_model=ProductsResponse)
def list_products() -> ProductsResponse:
    return ProductsResponse(products=procurement_service.list_products())


@router.get("/match", response_model=MatchResponse)
def match(q: str, limit: int = 5) -> MatchResponse:
    return MatchResponse(matches=procurement_service.match_products(q, limit))


@router.get("/products/{product_id}", response_model=ProductEstimateResponse)
def product_estimate(
    product_id: str,
    additional_product_ids: list[str] = Query(default=[]),
) -> ProductEstimateResponse:
    estimate = procurement_service.estimate_product(product_id, additional_product_ids)
    if estimate is None:
        raise HTTPException(status_code=404, detail="Для продукта нет расчётов стоимости")
    return estimate


@router.post("/for-tz/{tz_id}", response_model=TZEstimateResponse)
async def estimate_for_tz(
    tz_id: str,
    additional_product_ids: list[str] = Query(default=[]),
) -> TZEstimateResponse:
    document = await tz_repository.get(tz_id)
    if document is None:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    return procurement_service.estimate_for_tz(document, additional_product_ids)
