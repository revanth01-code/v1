from typing import Optional
from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    monthly_income: float = Field(ge=0, default=0)
    monthly_expenses: float = Field(ge=0, default=0)
    existing_savings: float = Field(ge=0, default=0)
    existing_investments: float = Field(ge=0, default=0)
    dependents: int = Field(ge=0, default=0)
    employment_type: Optional[str] = None


class ProfileUpdate(BaseModel):
    # All optional — this is a partial update (PATCH-style, even though
    # we expose it on PUT for simplicity). Only fields the client sends
    # get changed.
    monthly_income: Optional[float] = Field(default=None, ge=0)
    monthly_expenses: Optional[float] = Field(default=None, ge=0)
    existing_savings: Optional[float] = Field(default=None, ge=0)
    existing_investments: Optional[float] = Field(default=None, ge=0)
    dependents: Optional[int] = Field(default=None, ge=0)
    employment_type: Optional[str] = None


class ProfileOut(BaseModel):
    id: str
    user_id: str
    monthly_income: float
    monthly_expenses: float
    existing_savings: float
    existing_investments: float
    dependents: int
    employment_type: Optional[str] = None
    monthly_surplus: float  # derived, not stored — see service.py
    created_at: str
    updated_at: str