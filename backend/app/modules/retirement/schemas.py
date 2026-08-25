from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from app.core.constants import (
    DEFAULT_INFLATION_PCT,
    DEFAULT_LIFE_EXPECTANCY,
    DEFAULT_POST_RETIREMENT_RETURN_PCT,
    DEFAULT_PRE_RETIREMENT_RETURN_PCT,
)


class RetirementCreate(BaseModel):
    current_age: int = Field(ge=18, le=100)
    retirement_age: int = Field(ge=18, le=100)
    life_expectancy: int = Field(ge=1, le=120, default=DEFAULT_LIFE_EXPECTANCY)
    existing_retirement_corpus: float = Field(ge=0, default=0)
    planned_monthly_contribution: float = Field(ge=0, default=0)
    inflation_pct: float = Field(ge=0, default=DEFAULT_INFLATION_PCT)
    pre_retirement_return_pct: float = Field(ge=0, default=DEFAULT_PRE_RETIREMENT_RETURN_PCT)
    post_retirement_return_pct: float = Field(ge=0, default=DEFAULT_POST_RETIREMENT_RETURN_PCT)

    @model_validator(mode="after")
    def check_age_ordering(self):
        if self.retirement_age <= self.current_age:
            raise ValueError("retirement_age must be greater than current_age")
        if self.life_expectancy <= self.retirement_age:
            raise ValueError("life_expectancy must be greater than retirement_age")
        return self


class RetirementUpdate(BaseModel):
    current_age: Optional[int] = Field(default=None, ge=18, le=100)
    retirement_age: Optional[int] = Field(default=None, ge=18, le=100)
    life_expectancy: Optional[int] = Field(default=None, ge=1, le=120)
    existing_retirement_corpus: Optional[float] = Field(default=None, ge=0)
    planned_monthly_contribution: Optional[float] = Field(default=None, ge=0)
    inflation_pct: Optional[float] = Field(default=None, ge=0)
    pre_retirement_return_pct: Optional[float] = Field(default=None, ge=0)
    post_retirement_return_pct: Optional[float] = Field(default=None, ge=0)


class RetirementOut(BaseModel):
    id: str
    user_id: str
    current_age: int
    retirement_age: int
    life_expectancy: int
    existing_retirement_corpus: float
    planned_monthly_contribution: float
    inflation_pct: float
    pre_retirement_return_pct: float
    post_retirement_return_pct: float
    current_monthly_expense: float  # pulled fresh from financial_profile
    years_to_retirement: int
    years_in_retirement: int
    required_corpus: float
    feasibility_status: str  # 'feasible' | 'borderline' | 'infeasible'
    feasibility_details: dict
    created_at: datetime
    updated_at: datetime