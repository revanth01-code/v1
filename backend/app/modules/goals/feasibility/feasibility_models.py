# backend/app/modules/goals/feasibility/feasibility_models.py
from datetime import date
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field

class GoalFeasibilityPreviewRequest(BaseModel):
    target_amount: float = Field(gt=0)
    current_amount: float = Field(default=0.0, ge=0.0)
    monthly_investment: float = Field(default=0.0, ge=0.0)
    target_date: Optional[date] = None
    horizon_months: Optional[int] = Field(default=None, ge=1)
    risk_level: Literal["low", "mid", "high"] = "mid"

class GoalFeasibilityAlternative(BaseModel):
    type: Literal["increase_monthly_investment", "extend_horizon", "adjust_target", "review_risk_profile"]
    current_monthly_investment: Optional[float] = None
    recommended_monthly_investment: Optional[float] = None
    difference: Optional[float] = None
    current_horizon_months: Optional[int] = None
    recommended_horizon_months: Optional[int] = None
    additional_months: Optional[int] = None
    current_target_amount: Optional[float] = None
    projected_target_amount: Optional[float] = None
    description: str

class GoalFeasibilityPreviewResponse(BaseModel):
    status: Literal["ACHIEVABLE", "STRETCHED", "DIFFICULT", "UNREALISTIC", "INSUFFICIENT_INFORMATION"]
    reason: Optional[str] = None
    goal_summary: dict
    projection: Optional[dict] = None
    assumptions: dict
    alternatives: list[GoalFeasibilityAlternative]
    next_step: str

class GoalFeasibilityApplyRequest(BaseModel):
    original_goal: GoalFeasibilityPreviewRequest
    selected_alternative: GoalFeasibilityAlternative

class GoalFeasibilityApplyResponse(BaseModel):
    status: str
    revised_goal: GoalFeasibilityPreviewRequest
    strategy_preview: dict
