# backend/app/modules/universe/recommendation/schemas.py
from datetime import date
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field
from app.modules.tax.tax_service import TaxProfile

class UserPreferences(BaseModel):
    growth_vs_stability: Optional[Literal["growth", "balanced", "stability"]] = None
    liquidity_preference: Optional[Literal["high", "medium", "low"]] = None
    tax_optimization_preference: Optional[bool] = None
    accept_lock_in: Optional[bool] = None
    investment_style: Optional[Literal["aggressive", "balanced", "conservative"]] = None

class GoalStrategyFinalizeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200, default="Temporary Goal")
    target_amount: float = Field(gt=0)
    target_date: date
    risk_level: Literal["low", "mid", "high"]
    goal_type: Literal["vacation", "house", "car", "education", "wedding", "retirement", "healthcare", "custom"] = "custom"
    preferences: Optional[UserPreferences] = None
    tax_profile: Optional[TaxProfile] = None

class RecommendationCategoryPlan(BaseModel):
    category: str
    allocation_percent: float

class RecommendationPlan(BaseModel):
    categories: list[RecommendationCategoryPlan]
    selection_rules: list[str]

class GoalStrategyFinalizeResponse(BaseModel):
    strategy: dict
    user_preferences: Optional[UserPreferences] = None
    tax_summary: dict
    recommendation_plan: RecommendationPlan
    next_step: str = "view_recommendations"
