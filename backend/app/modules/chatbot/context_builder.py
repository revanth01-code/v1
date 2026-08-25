from app.core.exceptions import AppError
from app.modules.profile.service import ProfileService
from app.modules.goals.service import GoalService
from app.modules.retirement.service import RetirementService
from app.modules.emergency_fund.service import EmergencyFundService


def build_user_context(access_token: str, user_id: str) -> dict:
    """Assembles a compact, structured summary of everything the app knows
    about this user — profile, goals, retirement, emergency fund — for the
    chatbot's system prompt. Uses each module's SERVICE layer (not raw
    repository rows), so the numbers shown to the AI match exactly what the
    user sees elsewhere in the app (feasibility status, computed surplus,
    etc.), not stale/raw DB values.

    Any module the user hasn't set up yet degrades to None/[] rather than
    raising — a missing retirement plan shouldn't break the whole chat.
    """
    context: dict = {}

    try:
        profile = ProfileService.get_profile(access_token, user_id)
        context["profile"] = {
            "monthly_income": profile.monthly_income,
            "monthly_expenses": profile.monthly_expenses,
            "monthly_surplus": profile.monthly_surplus,
            "existing_savings": profile.existing_savings,
            "existing_investments": profile.existing_investments,
            "dependents": profile.dependents,
            "employment_type": profile.employment_type,
        }
    except AppError:
        context["profile"] = None

    try:
        goals = GoalService.list_goals(access_token, user_id)
        context["goals"] = [
            {
                "name": g.name,
                "target_amount": g.target_amount,
                "target_date": g.target_date.isoformat(),
                "risk_level": g.risk_level,
                "feasibility_status": g.feasibility_status,
                "monthly_contribution": g.monthly_contribution,
            }
            for g in goals
        ]
    except AppError:
        context["goals"] = []

    try:
        retirement = RetirementService.get(access_token, user_id)
        context["retirement"] = {
            "current_age": retirement.current_age,
            "retirement_age": retirement.retirement_age,
            "required_corpus": retirement.required_corpus,
            "planned_monthly_contribution": retirement.planned_monthly_contribution,
            "feasibility_status": retirement.feasibility_status,
        }
    except AppError:
        context["retirement"] = None

    try:
        ef = EmergencyFundService.get(access_token, user_id)
        context["emergency_fund"] = {
            "target_amount": ef.target_amount,
            "current_amount": ef.current_amount,
            "status": ef.status,
            "time_to_target_months": ef.time_to_target_months,
        }
    except AppError:
        context["emergency_fund"] = None

    return context