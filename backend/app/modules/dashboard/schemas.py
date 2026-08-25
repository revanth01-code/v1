from typing import Optional
from pydantic import BaseModel


class GoalSummary(BaseModel):
    id: str
    name: str
    target_amount: float
    target_date: str
    feasibility_status: str


class GoalsOverview(BaseModel):
    total: int
    feasible: int
    borderline: int
    items: list[GoalSummary]


class RetirementOverview(BaseModel):
    required_corpus: float
    feasibility_status: str
    years_to_retirement: int


class EmergencyFundOverview(BaseModel):
    target_amount: float
    current_amount: float
    status: str


class DashboardOut(BaseModel):
    profile_complete: bool
    goals: GoalsOverview
    retirement: Optional[RetirementOverview] = None
    emergency_fund: Optional[EmergencyFundOverview] = None