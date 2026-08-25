from fastapi import APIRouter, Query
from app.core.constants import FUND_CATEGORIES
from app.core.exceptions import AppError
from .schemas import FundDetailOut, FundOut
from .service import FundService

router = APIRouter(prefix="/funds", tags=["funds"])


@router.get("", response_model=list[FundOut])
def list_funds(
    category: str = Query(..., description="One of: " + ", ".join(FUND_CATEGORIES)),
    limit: int = Query(10, ge=1, le=50),
):
    if category not in FUND_CATEGORIES:
        raise AppError(f"category must be one of: {', '.join(FUND_CATEGORIES)}", 422)
    return FundService.get_funds_by_category(category, limit)


@router.get("/{scheme_code}", response_model=FundDetailOut)
def get_fund(scheme_code: str):
    return FundService.get_fund_detail(scheme_code)