from datetime import date, datetime
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field, model_validator
from app.modules.funds.schemas import FundOut


class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    target_amount: float = Field(gt=0)
    target_date: date
    contribution_mode: Literal["sip", "lumpsum", "both"]
    monthly_contribution: float = Field(ge=0, default=0)
    lumpsum_amount: float = Field(ge=0, default=0)
    risk_level: Literal["low", "mid", "high"]
    goal_type: Literal["vacation", "house", "car", "education", "wedding", "retirement", "healthcare", "custom"] = "custom"
    priority: Literal["low", "medium", "high"] = "medium"
    deadline_flexibility: Literal["flexible", "semi-flexible", "inflexible"] = "flexible"
    importance: Literal["optional", "important", "mandatory"] = "important"
    inflation_scenario: Literal["conservative", "expected", "high"] = "expected"
    inflation_rate_override: Optional[float] = Field(default=None, ge=0)
    priority_rank: Optional[int] = Field(default=None, ge=1, description="Optional 1-based user defined priority rank")

    @model_validator(mode="after")
    def check_contribution_matches_mode(self):
        if self.contribution_mode == "sip" and self.monthly_contribution <= 0:
            raise ValueError("monthly_contribution must be > 0 when contribution_mode is 'sip'")
        if self.contribution_mode == "lumpsum" and self.lumpsum_amount <= 0:
            raise ValueError("lumpsum_amount must be > 0 when contribution_mode is 'lumpsum'")
        if self.contribution_mode == "both" and self.monthly_contribution <= 0 and self.lumpsum_amount <= 0:
            raise ValueError("at least one of monthly_contribution or lumpsum_amount must be > 0")
        return self


class GuardrailResult(BaseModel):
    allowed: bool
    warning: Optional[str] = None


class GoalCheckResponse(BaseModel):
    term_type: Literal["short_term", "long_term"]
    guardrail: GuardrailResult
    feasibility: dict  # FeasibilityResult, kept loose here to avoid a circular import
    strategies: Optional[dict] = None


class GoalOut(BaseModel):
    id: str
    user_id: str
    name: str
    target_amount: float
    target_date: date
    term_type: str
    contribution_mode: str
    monthly_contribution: float
    lumpsum_amount: float
    risk_level: str
    fund_category_mix: dict
    expected_return_pct: float
    inflation_adjusted_target: float
    feasibility_status: str
    feasibility_details: Optional[dict] = None
    status: str
    created_at: datetime
    updated_at: datetime
    goal_type: str = "custom"
    priority: str = "medium"
    deadline_flexibility: str = "flexible"
    importance: str = "important"
    inflation_scenario: str = "expected"
    inflation_rate_pct: float = 6.0
    inflation_rate_override: Optional[float] = None
    priority_rank: Optional[int] = None
    strategies: Optional[dict] = None
    recommended_funds: dict[str, list[FundOut]] = Field(default_factory=dict)


class GoalStrategyPreviewRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200, default="Temporary Goal")
    target_amount: float = Field(gt=0)
    target_date: date
    risk_level: Literal["low", "mid", "high"]
    goal_type: Literal["vacation", "house", "car", "education", "wedding", "retirement", "healthcare", "custom"] = "custom"
    tax_profile: Optional[Any] = None  # Will be mapped to TaxProfile schema at runtime/validation


class GoalStrategyPreviewResponse(BaseModel):
    strategy: dict
    tax_summary: dict
    next_step: str = "review_strategy"