import structlog
from typing import Any, Optional
from datetime import date
from app.core.constants import DEFAULT_INFLATION_PCT, FUND_CATEGORY_MIX, RISK_RETURN_MAP
from app.core.exceptions import AppError, FeasibilityBlockedError
from app.lib.date_utils import months_between
from app.modules.feasibility_engine.schemas import FeasibilityInput
from app.modules.feasibility_engine.service import FeasibilityEngine
from .repository import GoalRepository
from .schemas import GoalCheckResponse, GoalCreate, GoalOut, GoalStrategyPreviewRequest
from .validators import derive_term_type, validate_risk_for_term
from app.modules.funds.service import FundService

logger = structlog.get_logger()

# Baseline inflation rate assumptions by goal category
BASE_INFLATION_MAP = {
    "education": 8.0,
    "vacation": 7.0,
    "house": 6.0,
    "healthcare": 8.0,
    "wedding": 7.0,
    "car": 5.0,
    "retirement": 6.0,
    "custom": 6.0
}


def get_inflation_rate(goal_type: str, scenario: str, override: float = None) -> float:
    if override is not None:
        return override
    base = BASE_INFLATION_MAP.get(goal_type.lower(), 6.0)
    if scenario == "conservative":
        return max(base - 2.0, 0.0)
    elif scenario == "high":
        return base + 2.0
    return base


def generate_goal_strategies(
    goal_type: str,
    months: int,
    importance: str,
    priority: str,
    flexibility: str,
    target_amount: float,
    funding_gap: float,
    current_progress: float,
    user_capacity: float
) -> dict:
    strategies = {}
    
    # Determine base parameters for three strategies based on timeframe & strategy
    for strategy_name in ["conservative", "moderate", "aggressive"]:
        if months <= 12:
            # Short-term: Capital protection & liquidity
            if strategy_name == "conservative":
                equity, debt = 0, 100
                ret_range = "6.0% - 7.0%"
                expected_return = 6.5
                volatility = "Very Low"
                liquidity = "Very High"
            elif strategy_name == "moderate":
                equity, debt = 10, 90
                ret_range = "6.5% - 7.5%"
                expected_return = 7.0
                volatility = "Low"
                liquidity = "High"
            else: # aggressive
                equity, debt = 20, 80
                ret_range = "7.0% - 8.5%"
                expected_return = 7.5
                volatility = "Low-Medium"
                liquidity = "High"
        elif months <= 60:
            # Medium-term: Balanced
            if strategy_name == "conservative":
                equity, debt = 20, 80
                ret_range = "7.0% - 8.0%"
                expected_return = 7.5
                volatility = "Low"
                liquidity = "High"
            elif strategy_name == "moderate":
                equity, debt = 40, 60
                ret_range = "8.5% - 10.0%"
                expected_return = 9.25
                volatility = "Medium"
                liquidity = "Medium-High"
            else: # aggressive
                equity, debt = 60, 40
                ret_range = "10.0% - 12.0%"
                expected_return = 11.0
                volatility = "Medium-High"
                liquidity = "Medium"
        else:
            # Long-term: Tolerates growth assets
            if strategy_name == "conservative":
                equity, debt = 40, 60
                ret_range = "8.0% - 9.5%"
                expected_return = 8.75
                volatility = "Medium-Low"
                liquidity = "Medium-High"
            elif strategy_name == "moderate":
                equity, debt = 70, 30
                ret_range = "10.5% - 12.0%"
                expected_return = 11.25
                volatility = "Medium"
                liquidity = "Medium"
            else: # aggressive
                equity, debt = 90, 10
                ret_range = "12.5% - 14.5%"
                expected_return = 13.5
                volatility = "High"
                liquidity = "Medium-Low"
                
        # Estimate probability of success
        if months <= 12:
            prob = 95 if strategy_name == "conservative" else (80 if strategy_name == "moderate" else 55)
        elif months <= 60:
            prob = 90 if strategy_name == "conservative" else (85 if strategy_name == "moderate" else 70)
        else:
            prob = 88 if strategy_name == "conservative" else (87 if strategy_name == "moderate" else 80)
            
        # Adjust based on user deadline flexibility
        if flexibility == "flexible":
            prob = min(prob + 10, 99)
        elif flexibility == "inflexible":
            prob = max(prob - 10, 20)
            
        # Adjust based on importance
        if importance == "mandatory" and strategy_name == "aggressive":
            prob = max(prob - 8, 15)
        elif importance == "optional" and strategy_name == "aggressive":
            prob = min(prob + 5, 95)
            
        strategies[strategy_name] = {
            "risk_level": "Low" if strategy_name == "conservative" else ("Medium" if strategy_name == "moderate" else "High"),
            "equity_pct": equity,
            "debt_pct": debt,
            "expected_return_range": ret_range,
            "expected_return_pct": expected_return,
            "volatility": volatility,
            "liquidity": liquidity,
            "success_probability": prob
        }
        
    return strategies


def _run_check(payload: GoalCreate) -> tuple[str, dict, dict, dict]:
    months = months_between(date.today(), payload.target_date)
    term_type = derive_term_type(months)
    guardrail = validate_risk_for_term(months, payload.risk_level)

    expected_return_pct = RISK_RETURN_MAP[payload.risk_level]
    inflation_rate = get_inflation_rate(
        payload.goal_type, 
        payload.inflation_scenario, 
        payload.inflation_rate_override
    )
    
    feasibility_input = FeasibilityInput(
        target_amount=payload.target_amount,
        target_date=payload.target_date,
        monthly_contribution=payload.monthly_contribution,
        lumpsum_amount=payload.lumpsum_amount,
        expected_return_pct=expected_return_pct,
        inflation_pct=inflation_rate,
    )
    feasibility = FeasibilityEngine.check(feasibility_input)
    
    funding_gap = feasibility.shortfall or 0.0
    current_progress = 0.0
    if payload.target_amount > 0:
        current_progress = payload.lumpsum_amount / payload.target_amount

    strategies = generate_goal_strategies(
        goal_type=payload.goal_type,
        months=months,
        importance=payload.importance,
        priority=payload.priority,
        flexibility=payload.deadline_flexibility,
        target_amount=payload.target_amount,
        funding_gap=funding_gap,
        current_progress=current_progress,
        user_capacity=0.0
    )

    return term_type, guardrail.model_dump(), feasibility.model_dump(), strategies


FUNDS_PER_CATEGORY = 2


def _attach_recommended_funds(fund_category_mix: dict) -> dict[str, list[dict]]:
    recommended: dict[str, list[dict]] = {}
    for category in fund_category_mix.keys():
        try:
            funds = FundService.get_funds_by_category(category, limit=FUNDS_PER_CATEGORY)
            recommended[category] = [f.model_dump() for f in funds]
        except Exception:
            recommended[category] = []
    return recommended


def _enrich_goal_out(row: dict) -> dict:
    from datetime import datetime
    target_date_val = row["target_date"]
    if isinstance(target_date_val, str):
        target_date = date.fromisoformat(target_date_val)
    else:
        target_date = target_date_val

    months = months_between(date.today(), target_date)
    
    feas_details = row.get("feasibility_details") or {}
    funding_gap = feas_details.get("shortfall") or 0.0
    
    target_amount = row.get("target_amount") or 0.0
    lumpsum_amount = row.get("lumpsum_amount") or 0.0
    current_progress = 0.0
    if target_amount > 0:
        current_progress = lumpsum_amount / target_amount
        
    strategies = generate_goal_strategies(
        goal_type=row.get("goal_type", "custom"),
        months=months,
        importance=row.get("importance", "important"),
        priority=row.get("priority", "medium"),
        flexibility=row.get("deadline_flexibility", "flexible"),
        target_amount=target_amount,
        funding_gap=funding_gap,
        current_progress=current_progress,
        user_capacity=0.0
    )
    
    return {
        **row,
        "strategies": strategies
    }


class GoalService:
    @staticmethod
    def check(payload: GoalCreate) -> GoalCheckResponse:
        term_type, guardrail, feasibility, strategies = _run_check(payload)
        return GoalCheckResponse(
            term_type=term_type, 
            guardrail=guardrail, 
            feasibility=feasibility,
            strategies=strategies
        )

    @staticmethod
    def create(access_token: str, user_id: str, payload: GoalCreate) -> GoalOut:
        log = logger.bind(user_id=user_id, goal_name=payload.name)
        log.info("goal_create_started", target_amount=payload.target_amount, contribution_mode=payload.contribution_mode)

        term_type, guardrail, feasibility, strategies = _run_check(payload)
        log.info("goal_feasibility_checked", feasibility_status=feasibility.get("status"), term_type=term_type)

        if not guardrail["allowed"]:
            raise AppError(guardrail["warning"], 422)

        # Block goal creation if status is At Risk or Unlikely
        if feasibility["status"] in ("unlikely", "at_risk"):
            raise FeasibilityBlockedError(
                "This goal is not achievable with your current plan. "
                "Adjust your contribution, timeline, or risk level and try again.",
                feasibility=feasibility,
            )

        expected_return_pct = RISK_RETURN_MAP[payload.risk_level]
        
        # Map the feasibility status to fit the database check constraint.
        # DB check constraint allows: 'feasible', 'borderline', 'infeasible'
        raw_status = feasibility["status"]
        db_feasibility_status = "feasible"
        if raw_status == "borderline":
            db_feasibility_status = "borderline"
        elif raw_status in ("at_risk", "unlikely"):
            db_feasibility_status = "infeasible"

        inflation_rate = get_inflation_rate(
            payload.goal_type, 
            payload.inflation_scenario, 
            payload.inflation_rate_override
        )

        row_payload = {
            "name": payload.name,
            "target_amount": payload.target_amount,
            "target_date": payload.target_date.isoformat(),
            "term_type": term_type,
            "contribution_mode": payload.contribution_mode,
            "monthly_contribution": payload.monthly_contribution,
            "lumpsum_amount": payload.lumpsum_amount,
            "risk_level": payload.risk_level,
            "fund_category_mix": FUND_CATEGORY_MIX[payload.risk_level],
            "expected_return_pct": expected_return_pct,
            "inflation_adjusted_target": feasibility["inflation_adjusted_target"],
            "feasibility_status": db_feasibility_status,
            "feasibility_details": feasibility,
            "goal_type": payload.goal_type,
            "priority": payload.priority,
            "deadline_flexibility": payload.deadline_flexibility,
            "importance": payload.importance,
            "inflation_scenario": payload.inflation_scenario,
            "inflation_rate_pct": inflation_rate,
            "inflation_rate_override": payload.inflation_rate_override,
            "priority_rank": payload.priority_rank,
        }

        log.info("goal_db_insert_started", feasibility_status=db_feasibility_status)
        row = GoalRepository.create(access_token, user_id, row_payload)
        log.info("goal_db_insert_completed", goal_id=row.get("id"))

        enriched = _enrich_goal_out(row)
        log.info("goal_fund_attachment_started", categories=list(row["fund_category_mix"].keys()))
        funds = _attach_recommended_funds(row["fund_category_mix"])
        log.info("goal_create_completed", goal_id=row.get("id"))
        return GoalOut(**enriched, recommended_funds=funds)

    @staticmethod
    def list_goals(access_token: str, user_id: str, limit: int = 20, offset: int = 0, attach_funds: bool = False) -> list[GoalOut]:
        rows = GoalRepository.list_by_user(access_token, user_id, limit=limit, offset=offset)
        res = []
        for row in rows:
            enriched = _enrich_goal_out(row)
            funds = _attach_recommended_funds(row["fund_category_mix"]) if attach_funds else {}
            res.append(GoalOut(**enriched, recommended_funds=funds))
        return res
    
    @staticmethod
    def get_goal(access_token: str, user_id: str, goal_id: str) -> GoalOut:
        row = GoalRepository.get_by_id(access_token, user_id, goal_id)
        if not row:
            raise AppError("Goal not found", 404)
        enriched = _enrich_goal_out(row)
        return GoalOut(**enriched, recommended_funds=_attach_recommended_funds(row["fund_category_mix"]))

    @staticmethod
    def preview_strategy(payload: GoalStrategyPreviewRequest) -> dict:
        from app.modules.tax.tax_service import TaxProfile, TaxOpportunityService
        
        # 1. Proposed strategy build
        from app.core.constants import FUND_CATEGORY_MIX
        
        # Calculate months
        months = months_between(date.today(), payload.target_date)
        horizon_years = round(months / 12, 1)
        
        mix = FUND_CATEGORY_MIX[payload.risk_level]
        
        equity = 0
        debt = 0
        diversifier = 0
        for cat, pct in mix.items():
            if cat in ["largecap", "flexicap", "midcap"]:
                equity += pct
            elif cat == "debt":
                debt += pct
                
        formatted_mix = [{"category": cat, "allocation_percent": pct} for cat, pct in mix.items()]
        
        # Generate explanations
        reasoning = []
        if months < 36:
            reasoning.append(f"Your short-term investment horizon ({horizon_years} years) prioritizes capital preservation.")
        else:
            reasoning.append(f"Your {horizon_years}-year investment horizon allows moderate/higher equity exposure.")
            
        if payload.risk_level == "low":
            reasoning.append("Your selected risk level limits high-volatility categories and allocates more to debt.")
        elif payload.risk_level == "mid":
            reasoning.append("Your selected risk level balances growth and stability across equity and debt.")
        elif payload.risk_level == "high":
            reasoning.append("Your selected risk level prioritizes capital appreciation through pure equity allocation.")
            
        # Optional tax optimization note
        tax_profile_data = payload.tax_profile
        if tax_profile_data and tax_profile_data.get("wants_tax_optimization"):
            reasoning.append("Tax optimization preferences were considered separately from fund quality.")
            
        strategy = {
            "investment_horizon_years": horizon_years,
            "risk_level": payload.risk_level,
            "allocation": {
                "equity": equity,
                "debt": debt,
                "diversifier": diversifier
            },
            "fund_category_mix": formatted_mix,
            "reasoning": reasoning
        }
        
        # 2. Tax profile analysis
        tax_p = None
        if tax_profile_data:
            tax_p = TaxProfile(**tax_profile_data)
        tax_summary = TaxOpportunityService.analyze_profile(tax_p)
        
        return {
            "strategy": strategy,
            "tax_summary": tax_summary,
            "next_step": "review_strategy"
        }

    @staticmethod
    def finalize_strategy(payload: Any) -> dict:
        from app.modules.tax.tax_service import TaxProfile, TaxOpportunityService
        from app.core.constants import FUND_CATEGORY_MIX
        
        preferences = payload.preferences
        tax_profile = payload.tax_profile
        
        # Calculate horizon
        months = months_between(date.today(), payload.target_date)
        horizon_years = round(months / 12, 1)
        
        base_mix = FUND_CATEGORY_MIX[payload.risk_level]
        
        # Adjust mix if ELSS conditions are met
        final_mix = adjust_mix_for_tax(base_mix, preferences, tax_profile)
        
        equity = 0
        debt = 0
        diversifier = 0
        for cat, pct in final_mix.items():
            if cat in ["largecap", "flexicap", "midcap", "elss"]:
                equity += pct
            elif cat == "debt":
                debt += pct
                
        formatted_mix = [{"category": cat, "allocation_percent": pct} for cat, pct in final_mix.items()]
        
        # Generate explanations
        reasoning = []
        if months < 36:
            reasoning.append(f"Your short-term investment horizon ({horizon_years} years) prioritizes capital preservation.")
        else:
            reasoning.append(f"Your {horizon_years}-year investment horizon allows moderate/higher equity exposure.")
            
        if payload.risk_level == "low":
            reasoning.append("Your selected risk level limits high-volatility categories and allocates more to debt.")
        elif payload.risk_level == "mid":
            reasoning.append("Your selected risk level balances growth and stability across equity and debt.")
        elif payload.risk_level == "high":
            reasoning.append("Your selected risk level prioritizes capital appreciation through pure equity allocation.")
            
        if preferences and preferences.tax_optimization_preference:
            reasoning.append("Tax optimization preferences were considered separately from fund quality.")
            
        strategy = {
            "investment_horizon_years": horizon_years,
            "risk_level": payload.risk_level,
            "allocation": {
                "equity": equity,
                "debt": debt,
                "diversifier": diversifier
            },
            "fund_category_mix": formatted_mix,
            "reasoning": reasoning
        }
        
        # Tax opportunity analysis
        tax_summary = TaxOpportunityService.analyze_profile(tax_profile)
        
        # Build selection rules
        selection_rules = [
            "Exclude funds with INSUFFICIENT data confidence.",
            "Exclude funds without a calculated peer recommendation score.",
            "Rank funds primarily by recommendation_score descending within each category.",
            "Sort secondarily by data_confidence priority: HIGH, MEDIUM, LOW.",
            "Resolve final ties alphabetically by asset name."
        ]
        if "elss" in final_mix:
            selection_rules.append(
                "ELSS is being considered because you selected tax optimization and indicated that you can accept a 3-year lock-in."
            )
            
        plan_categories = [{"category": cat, "allocation_percent": pct} for cat, pct in final_mix.items()]
        recommendation_plan = {
            "categories": plan_categories,
            "selection_rules": selection_rules
        }
        
        return {
            "strategy": strategy,
            "user_preferences": preferences,
            "tax_summary": tax_summary,
            "recommendation_plan": recommendation_plan,
            "next_step": "view_recommendations"
        }

    @staticmethod
    def get_recommendations_preview(payload: Any) -> dict:
        from datetime import datetime, timezone
        
        # 1. Finalize strategy to get the correct fund mix (including any tax adjustment)
        finalize_result = GoalService.finalize_strategy(payload)
        
        strategy = finalize_result["strategy"]
        tax_summary = finalize_result["tax_summary"]
        
        # Build category mix dict from strategy
        mix_dict = {item["category"]: item["allocation_percent"] for item in strategy["fund_category_mix"]}
        
        # 2. Get recommendations
        from app.modules.universe.recommendation.recommendation_service import RecommendationService
        recommendations = RecommendationService.get_recommendations(
            fund_category_mix=mix_dict,
            investment_horizon_years=strategy["investment_horizon_years"],
            risk_level=strategy["risk_level"],
            preferences=payload.preferences,
            tax_profile=payload.tax_profile
        )
        
        engine_metadata = {
            "ranking_method": "deterministic_peer_scoring",
            "scoring_version": "1.1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": "Recommendations are generated using historical data and deterministic evaluation metrics and should not be considered guaranteed future performance."
        }
        
        return {
            "strategy": strategy,
            "tax_summary": tax_summary,
            "recommendations": recommendations,
            "engine_metadata": engine_metadata
        }


def adjust_mix_for_tax(mix: dict, preferences: Optional[Any], tax_profile: Optional[Any]) -> dict:
    if not preferences or not tax_profile:
        return mix
    
    # Check 3 conditions:
    # 1. Tax optimization is requested
    # 2. Section 80C opportunity exists (i.e. regime is not new, and remaining limit > 0)
    # 3. User accepts lock-in
    tax_opt = getattr(preferences, "tax_optimization_preference", None)
    lock_in = getattr(preferences, "accept_lock_in", None)
    
    if not (tax_opt is True and lock_in is True):
        return mix
    
    tax_regime = getattr(tax_profile, "tax_regime", "unknown")
    if tax_regime == "new":
        return mix
    
    existing_investments = getattr(tax_profile, "existing_tax_saving_investments_range", 0.0)
    remaining_80c = 150000.0 - existing_investments
    if remaining_80c <= 0:
        return mix
        
    # If eligible, allocate 15% to ELSS.
    # We take the 15% from the non-debt categories.
    new_mix = mix.copy()
    non_debt_cats = [c for c in new_mix.keys() if c != "debt"]
    if not non_debt_cats:
        return mix  # No equity to take from
        
    elss_allocation = 15.0
    # Proportional subtraction
    total_non_debt = sum(new_mix[c] for c in non_debt_cats)
    if total_non_debt <= 0:
        return mix
        
    for c in non_debt_cats:
        deduction = (new_mix[c] / total_non_debt) * elss_allocation
        new_mix[c] = round(max(0.0, new_mix[c] - deduction), 2)
        
    new_mix["elss"] = elss_allocation
    return new_mix