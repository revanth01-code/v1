from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class EmergencyFundCreate(BaseModel):
    months_of_coverage: float = Field(gt=0, default=3)
    current_amount: float = Field(ge=0, default=0)
    monthly_contribution: float = Field(ge=0, default=0)


class EmergencyFundUpdate(BaseModel):
    months_of_coverage: Optional[float] = Field(default=None, gt=0)
    current_amount: Optional[float] = Field(default=None, ge=0)
    monthly_contribution: Optional[float] = Field(default=None, ge=0)


class EmergencyFundOut(BaseModel):
    id: str
    user_id: str
    months_of_coverage: float
    current_amount: float
    monthly_contribution: float
    monthly_expenses: float  # pulled fresh from financial_profile, not stored here
    target_amount: float  # derived: monthly_expenses * months_of_coverage
    time_to_target_months: Optional[float] = None  # derived, null if contribution is 0
    status: Literal["building", "complete"]
    created_at: datetime
    updated_at: datetime