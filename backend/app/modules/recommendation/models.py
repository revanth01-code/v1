# backend/app/modules/recommendation/models.py
from datetime import date
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field
from app.modules.universe.recommendation.schemas import UserPreferences
from app.modules.tax.tax_service import TaxProfile
from app.modules.goals.feasibility.feasibility_models import GoalFeasibilityAlternative

class RecommendationRequestGoal(BaseModel):
    goal_name: str = Field(min_length=1, max_length=200, default="Temporary Goal")
    target_amount: float = Field(gt=0)
    current_amount: float = Field(default=0.0, ge=0.0)
    monthly_investment: float = Field(default=0.0, ge=0.0)
    horizon_months: Optional[int] = Field(default=None, ge=1)
    target_date: Optional[date] = None
    risk_level: Literal["low", "mid", "high"] = "mid"

class RecommendationRequestOptions(BaseModel):
    allow_stretched_goal: bool = False
    include_tax_review: bool = True
    max_funds_per_category: int = 3

class RecommendationRequest(BaseModel):
    goal: RecommendationRequestGoal
    preferences: Optional[UserPreferences] = None
    tax_profile: Optional[TaxProfile] = None
    options: Optional[RecommendationRequestOptions] = Field(default_factory=RecommendationRequestOptions)
    selected_alternative: Optional[GoalFeasibilityAlternative] = None

class RecommendationResponse(BaseModel):
    workflow_state: Literal["INSUFFICIENT_INFORMATION", "FEASIBILITY_REVIEW_REQUIRED", "STRATEGY_READY", "RECOMMENDATIONS_READY"]
    feasibility: dict
    strategy: Optional[dict] = None
    tax_summary: Optional[dict] = None
    recommendations: Optional[dict] = None
    disclaimers: list[str] = [
        "Mutual fund investments are subject to market risk.",
        "Past performance does not guarantee future returns.",
        "Recommendations are generated using historical and peer-relative metrics."
    ]
