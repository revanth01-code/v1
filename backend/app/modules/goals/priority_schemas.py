# backend/app/modules/goals/priority_schemas.py
from datetime import date
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field


class GoalRankItem(BaseModel):
    goal_id: str = Field(..., description="ID of the goal to rank")
    priority_rank: int = Field(..., gt=0, description="1-based priority rank (1 is highest)")


class PriorityRankIn(BaseModel):
    rankings: list[GoalRankItem]


class ConflictWarning(BaseModel):
    code: str = Field(..., description="Code identifying the warning type")
    severity: Literal["WARNING", "INFO"] = Field(..., description="Severity level")
    message: str = Field(..., description="User-facing descriptive warning message")
    affected_goal_ids: list[str] = Field(default_factory=list, description="IDs of goals affected by this warning")


class PrioritySuggestion(BaseModel):
    goal_id: str = Field(..., description="ID of the goal associated with this suggestion")
    current_rank: Optional[int] = Field(None, description="Current rank assigned by the user")
    suggested_rank: int = Field(..., description="Suggested rank for financial optimization")
    reason: str = Field(..., description="Detailed explanation for the suggestion")


class CapacitySummary(BaseModel):
    monthly_income: float = 0.0
    monthly_expenses: float = 0.0
    essential_expenses: float = 0.0
    emi_obligations: float = 0.0
    mandatory_commitments: float = 0.0
    emergency_fund_contribution: float = 0.0
    available_capacity: float = 0.0
    total_monthly_contributions: float = 0.0
    surplus_shortfall: float = 0.0
    is_overcommitted: bool = False


class PriorityAnalysisOut(BaseModel):
    goals: list[Any] = Field(..., description="List of goals ordered by priority rank")
    warnings: list[ConflictWarning] = Field(default_factory=list, description="List of conflict warnings")
    suggestions: list[PrioritySuggestion] = Field(default_factory=list, description="List of strategic recommendations")
    capacity_summary: CapacitySummary = Field(..., description="Summary of user's financial capacity vs goal requirements")
    strategic_reasoning: list[str] = Field(default_factory=list, description="Strategic reasoning summary and multi-goal advice")
