from app.core.exceptions import AppError
from app.modules.profile.service import ProfileService
from app.modules.goals.service import GoalService
from app.modules.retirement.service import RetirementService
from app.modules.emergency_fund.service import EmergencyFundService
from .schemas import (
    DashboardOut,
    EmergencyFundOverview,
    GoalSummary,
    GoalsOverview,
    RetirementOverview,
)


class DashboardService:
    @staticmethod
    def get_summary(access_token: str, user_id: str) -> DashboardOut:
        # Profile completeness
        try:
            ProfileService.get_profile(access_token, user_id)
            profile_complete = True
        except AppError:
            profile_complete = False

        # Goals — always present as a list, never null
        goals = GoalService.list_goals(access_token, user_id)
        goals_overview = GoalsOverview(
            total=len(goals),
            feasible=sum(1 for g in goals if g.feasibility_status == "feasible"),
            borderline=sum(1 for g in goals if g.feasibility_status == "borderline"),
            items=[
                GoalSummary(
                    id=g.id,
                    name=g.name,
                    target_amount=g.target_amount,
                    target_date=g.target_date.isoformat(),
                    feasibility_status=g.feasibility_status,
                )
                for g in goals
            ],
        )

        # Retirement — optional, null if not set up yet
        retirement_overview = None
        try:
            retirement = RetirementService.get(access_token, user_id)
            retirement_overview = RetirementOverview(
                required_corpus=retirement.required_corpus,
                feasibility_status=retirement.feasibility_status,
                years_to_retirement=retirement.years_to_retirement,
            )
        except AppError:
            pass

        # Emergency fund — optional, null if not set up yet
        emergency_fund_overview = None
        try:
            ef = EmergencyFundService.get(access_token, user_id)
            emergency_fund_overview = EmergencyFundOverview(
                target_amount=ef.target_amount,
                current_amount=ef.current_amount,
                status=ef.status,
            )
        except AppError:
            pass

        return DashboardOut(
            profile_complete=profile_complete,
            goals=goals_overview,
            retirement=retirement_overview,
            emergency_fund=emergency_fund_overview,
        )