from datetime import date
from app.core.constants import DEFAULT_INFLATION_PCT, FUND_CATEGORY_MIX, RISK_RETURN_MAP
from app.core.exceptions import AppError, FeasibilityBlockedError
from app.lib.date_utils import months_between
from app.modules.feasibility_engine.schemas import FeasibilityInput
from app.modules.feasibility_engine.service import FeasibilityEngine
from .repository import GoalRepository
from .schemas import GoalCheckResponse, GoalCreate, GoalOut
from .validators import derive_term_type, validate_risk_for_term
from app.modules.funds.service import FundService


def _run_check(payload: GoalCreate) -> tuple[str, dict, dict]:
    """Shared by both /check and create — computes term_type, guardrail
    result, and the feasibility result for a given input."""
    months = months_between(date.today(), payload.target_date)
    term_type = derive_term_type(months)
    guardrail = validate_risk_for_term(months, payload.risk_level)

    expected_return_pct = RISK_RETURN_MAP[payload.risk_level]
    feasibility_input = FeasibilityInput(
        target_amount=payload.target_amount,
        target_date=payload.target_date,
        monthly_contribution=payload.monthly_contribution,
        lumpsum_amount=payload.lumpsum_amount,
        expected_return_pct=expected_return_pct,
        inflation_pct=DEFAULT_INFLATION_PCT,
    )
    feasibility = FeasibilityEngine.check(feasibility_input)

    return term_type, guardrail.model_dump(), feasibility.model_dump()

FUNDS_PER_CATEGORY = 2


def _attach_recommended_funds(fund_category_mix: dict) -> dict[str, list[dict]]:
    """Pulls real fund names per category from the funds module (Module 7).
    Degrades gracefully — if fund data is temporarily unavailable, goals
    still return normally, just with an empty recommendation list rather
    than failing the whole request."""
    recommended: dict[str, list[dict]] = {}
    for category in fund_category_mix.keys():
        try:
            funds = FundService.get_funds_by_category(category, limit=FUNDS_PER_CATEGORY)
            recommended[category] = [f.model_dump() for f in funds]
        except Exception:
            recommended[category] = []
    return recommended


class GoalService:
    @staticmethod
    def check(payload: GoalCreate) -> GoalCheckResponse:
        term_type, guardrail, feasibility = _run_check(payload)
        return GoalCheckResponse(term_type=term_type, guardrail=guardrail, feasibility=feasibility)

    @staticmethod
    def create(access_token: str, user_id: str, payload: GoalCreate) -> GoalOut:
        term_type, guardrail, feasibility = _run_check(payload)

        if not guardrail["allowed"]:
            raise AppError(guardrail["warning"], 422)

        if feasibility["status"] == "infeasible":
            raise FeasibilityBlockedError(
                "This goal isn't achievable with your current plan. "
                "Adjust your contribution, timeline, or risk level and try again.",
                feasibility=feasibility,
            )

        expected_return_pct = RISK_RETURN_MAP[payload.risk_level]
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
            "feasibility_status": feasibility["status"],  # 'feasible' or 'borderline' only, infeasible is blocked above
            "feasibility_details": feasibility,
        }

        row = GoalRepository.create(access_token, user_id, row_payload)
        return GoalOut(**row, recommended_funds=_attach_recommended_funds(row["fund_category_mix"]))

    @staticmethod
    def list_goals(access_token: str, user_id: str) -> list[GoalOut]:
        rows = GoalRepository.list_by_user(access_token, user_id)
        return [
            GoalOut(**row, recommended_funds=_attach_recommended_funds(row["fund_category_mix"]))
            for row in rows
        ]
    
    @staticmethod
    def get_goal(access_token: str, user_id: str, goal_id: str) -> GoalOut:
        row = GoalRepository.get_by_id(access_token, user_id, goal_id)
        if not row:
            raise AppError("Goal not found", 404)
        return GoalOut(**row, recommended_funds=_attach_recommended_funds(row["fund_category_mix"]))