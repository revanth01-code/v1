from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field


class FeasibilityInput(BaseModel):
    target_amount: float = Field(gt=0)
    target_date: date
    monthly_contribution: float = Field(ge=0, default=0)
    lumpsum_amount: float = Field(ge=0, default=0)
    expected_return_pct: float = Field(ge=0)
    inflation_pct: float = Field(ge=0, default=6.0)
    start_date: Optional[date] = None  # defaults to today if not provided


class FeasibilityResult(BaseModel):
    status: Literal["feasible", "borderline", "infeasible"]
    months: int
    inflation_adjusted_target: float
    projected_value: float
    shortfall: Optional[float] = None
    suggested_monthly_sip: Optional[float] = None
    suggested_extended_months: Optional[int] = None
    message: Optional[str] = None