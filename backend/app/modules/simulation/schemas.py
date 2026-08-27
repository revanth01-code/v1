# backend/app/modules/simulation/schemas.py
from typing import Literal, Optional
from pydantic import BaseModel, Field


class SimulationInput(BaseModel):
    lumpsum_amount: float = Field(ge=0, default=0.0)
    monthly_contribution: float = Field(ge=0, default=0.0)
    target_amount: float = Field(gt=0)
    target_date: str  # YYYY-MM-DD
    risk_level: Literal["low", "mid", "high", "custom"] = "mid"
    equity_pct: Optional[float] = Field(ge=0, le=100, default=None)
    debt_pct: Optional[float] = Field(ge=0, le=100, default=None)
    inflation_pct: float = Field(ge=0, default=6.0)
    stress_scenario: Literal[
        "none",
        "market_downturn",
        "high_inflation",
        "low_return",
        "sip_pause",
        "reduced_income",
        "increased_cost"
    ] = "none"
    sip_pause_start: int = Field(ge=0, default=0)
    sip_pause_duration: int = Field(ge=0, default=0)
    sip_reduce_pct: float = Field(ge=0, le=100, default=0.0)
    sip_reduce_start: int = Field(ge=0, default=0)
    sip_reduce_duration: int = Field(ge=0, default=0)


class SimulationResult(BaseModel):
    median_corpus: float
    mean_corpus: float
    downside_percentile_10: float
    upside_percentile_90: float
    prob_success: float
    prob_shortfall: float
    median_shortfall: float
    expected_shortfall: float
    purchasing_power_median: float
    adjusted_target: float
    message: str


class WhatIfComparisonResponse(BaseModel):
    current_plan: SimulationResult
    what_if_plan: SimulationResult
