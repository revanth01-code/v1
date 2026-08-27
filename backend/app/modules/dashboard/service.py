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
            feasible=sum(1 for g in goals if g.feasibility_status in ("feasible", "highly_feasible")),
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

        # Available Capacity & Total required SIP & Alerts
        available_capacity = 0.0
        total_required_sip = 0.0
        profile_dict = {}
        alerts = []
        
        try:
            profile = ProfileService.get_profile(access_token, user_id)
            available_capacity = getattr(profile, "available_capacity", 0.0)
            if hasattr(profile, "model_dump"):
                profile_dict = profile.model_dump()
            else:
                profile_dict = {}
        except Exception:
            pass
            
        total_required_sip = sum(g.monthly_contribution for g in goals if g.status == "active")
        
        if profile_dict:
            income = profile_dict.get("monthly_income") or 0.0
            essential = profile_dict.get("essential_expenses") or 0.0
            emi = profile_dict.get("emi_obligations") or 0.0
            mandatory = profile_dict.get("mandatory_commitments") or 0.0
            
            ef_contrib = 0.0
            ef_current = 0.0
            if emergency_fund_overview:
                try:
                    ef = EmergencyFundService.get(access_token, user_id)
                    ef_contrib = ef.monthly_contribution
                    ef_current = ef.current_amount
                except Exception:
                    ef_contrib = profile_dict.get("emergency_fund_contribution") or 0.0
            else:
                ef_contrib = profile_dict.get("emergency_fund_contribution") or 0.0
                
            # Alert 1 & 2: Over-allocation
            if total_required_sip > available_capacity:
                alerts.append(
                    f"Your total required monthly contribution across all goals is ₹{total_required_sip:,.2f}, "
                    f"while your estimated available investment capacity is ₹{available_capacity:,.2f}."
                )
                alerts.append(
                    f"Your active goals are competing for the same investment capacity. "
                    f"You are overallocated by ₹{total_required_sip - available_capacity:,.2f} per month."
                )
                
            # Alert 3: Multiple expensive goals near the same date
            close_goals = False
            for i in range(len(goals)):
                for j in range(i + 1, len(goals)):
                    if goals[i].status == "active" and goals[j].status == "active":
                        d1 = goals[i].target_date
                        d2 = goals[j].target_date
                        if abs((d1 - d2).days) <= 180:
                            close_goals = True
                            break
                if close_goals:
                    break
            if close_goals:
                alerts.append(
                    "You have multiple goals maturing within 6 months of each other. "
                    "Ensure you have adequate liquidity or sequential funding plans."
                )
                
            # Alert 4: Emergency money incorrectly counted toward investment goals
            total_lumpsum = sum(g.lumpsum_amount for g in goals if g.status == "active")
            savings = profile_dict.get("existing_savings") or 0.0
            investments = profile_dict.get("existing_investments") or 0.0
            total_assets = savings + investments
            
            if total_lumpsum > total_assets:
                alerts.append(
                    f"The total lumpsum funding allocated across your goals (₹{total_lumpsum:,.2f}) "
                    f"exceeds your total saved profile assets (₹{total_assets:,.2f})."
                )
            elif total_lumpsum > (total_assets - ef_current):
                alerts.append(
                    "Your planned lumpsum goal allocations may overlap with your emergency fund reserves. "
                    "Be cautious not to tap into emergency savings for long-term goals."
                )
                
            # Alert 5: Important goals underfunded
            underfunded_count = sum(
                1 for g in goals 
                if g.status == "active" 
                and g.importance in ("mandatory", "important") 
                and g.feasibility_status in ("at_risk", "unlikely")
            )
            if underfunded_count > 0:
                alerts.append(
                    f"You have {underfunded_count} important or mandatory goals that are currently underfunded (At Risk or Unlikely)."
                )

        return DashboardOut(
            profile_complete=profile_complete,
            goals=goals_overview,
            retirement=retirement_overview,
            emergency_fund=emergency_fund_overview,
            available_capacity=available_capacity,
            total_required_sip=total_required_sip,
            alerts=alerts,
        )