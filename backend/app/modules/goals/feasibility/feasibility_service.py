# backend/app/modules/goals/feasibility/feasibility_service.py
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import Optional, Any
from app.lib.date_utils import months_between
from .feasibility_models import (
    GoalFeasibilityPreviewRequest,
    GoalFeasibilityPreviewResponse,
    GoalFeasibilityAlternative,
    GoalFeasibilityApplyRequest,
    GoalFeasibilityApplyResponse
)

# Centralized Return assumptions
FEASIBILITY_RETURN_ASSUMPTIONS = {
    "low": {
        "conservative_return": 0.05,
        "moderate_return": 0.07,
    },
    "mid": {
        "conservative_return": 0.08,
        "moderate_return": 0.12,
    },
    "high": {
        "conservative_return": 0.11,
        "moderate_return": 0.15,
    }
}

PLANNING_DISCLAIMER = "Projected returns are estimates and are not guaranteed."


class FeasibilityService:
    @staticmethod
    def calculate_feasibility(payload: GoalFeasibilityPreviewRequest) -> GoalFeasibilityPreviewResponse:
        """Determines if the user's goal plan is feasible and suggests alternatives if needed.

        Decoupled from tax optimizations and fund rankings to preserve deterministic planning logic.
        """
        # Resolve target date and horizon months
        horizon_months = payload.horizon_months
        if horizon_months is None and payload.target_date is not None:
            horizon_months = months_between(date.today(), payload.target_date)

        # Check for insufficient information
        if horizon_months is None or horizon_months <= 0 or payload.target_amount <= 0:
            return GoalFeasibilityPreviewResponse(
                status="INSUFFICIENT_INFORMATION",
                reason="Target amount, monthly investment, or target date/horizon is missing or invalid.",
                goal_summary={
                    "target_amount": payload.target_amount,
                    "current_amount": payload.current_amount,
                    "monthly_investment": payload.monthly_investment,
                    "horizon_months": horizon_months or 0
                },
                assumptions={
                    "disclaimer": PLANNING_DISCLAIMER
                },
                alternatives=[],
                next_step="provide_missing_information"
            )

        # Get conservative return for planning
        risk = payload.risk_level
        assumptions = FEASIBILITY_RETURN_ASSUMPTIONS.get(risk, FEASIBILITY_RETURN_ASSUMPTIONS["mid"])
        annual_rate = assumptions["conservative_return"]
        r = annual_rate / 12.0

        # Calculations
        pv = payload.current_amount
        p_planned = payload.monthly_investment
        t = payload.target_amount

        # 1. Future Value of current lump sum: FV = PV * (1 + r)^n
        fv_lump = pv * ((1 + r) ** horizon_months)

        # 2. Future Value of SIP: FV = P * (((1 + r)^n - 1) / r) * (1 + r)
        if r > 0:
            sip_multiplier = (((1 + r) ** horizon_months - 1) / r) * (1 + r)
        else:
            sip_multiplier = horizon_months

        fv_sip = p_planned * sip_multiplier
        projected_value = round(fv_lump + fv_sip, 2)

        # 3. Required Monthly SIP: P_req = (T - fv_lump) / sip_multiplier
        gap = max(0.0, t - fv_lump)
        if sip_multiplier > 0:
            p_required = round(gap / sip_multiplier, 2)
        else:
            p_required = 0.0

        investment_gap = round(max(0.0, t - projected_value), 2)

        # Feasibility Classification logic based on percentage thresholds
        if p_required == 0.0 or p_planned >= p_required * 0.95:
            status = "ACHIEVABLE"
            reason = "Based on your planned monthly investment and selected planning assumptions, your goal appears achievable within the selected time horizon."
        elif p_planned >= p_required * 0.70:
            status = "STRETCHED"
            reason = "Your current investment plan may fall short of your target. A moderate increase in monthly investment or a longer investment horizon could improve feasibility."
        elif p_planned >= p_required * 0.40:
            status = "DIFFICULT"
            reason = "Your current plan has a significant gap relative to the target. Consider reviewing your investment amount, timeline, or target expectations."
        else:
            status = "UNREALISTIC"
            reason = "The current target may require investment amounts or return assumptions that are not reasonable for the selected risk profile."

        # Alternatives Generation
        alternatives = []
        if status in ["STRETCHED", "DIFFICULT", "UNREALISTIC"]:
            # A. Increase Monthly Investment
            diff = round(p_required - p_planned, 2)
            alternatives.append(GoalFeasibilityAlternative(
                type="increase_monthly_investment",
                current_monthly_investment=p_planned,
                recommended_monthly_investment=p_required,
                difference=diff,
                description=f"Increasing your monthly investment by ₹{diff:,.2f} improves the feasibility of reaching your target."
            ))

            # B. Extend Goal Horizon
            # Perform incremental month search
            recommended_months = horizon_months
            for test_n in range(horizon_months + 1, horizon_months + 240):
                test_fv_l = pv * ((1 + r) ** test_n)
                if r > 0:
                    test_sip_mult = (((1 + r) ** test_n - 1) / r) * (1 + r)
                else:
                    test_sip_mult = test_n
                test_fv_s = p_planned * test_sip_mult
                if (test_fv_l + test_fv_s) >= t:
                    recommended_months = test_n
                    break
            
            additional_months = recommended_months - horizon_months
            if additional_months > 0:
                alternatives.append(GoalFeasibilityAlternative(
                    type="extend_horizon",
                    current_horizon_months=horizon_months,
                    recommended_horizon_months=recommended_months,
                    additional_months=additional_months,
                    description=f"Extending your investment horizon by {additional_months} months reduces the monthly investment required."
                ))

            # C. Adjust Target Amount
            alternatives.append(GoalFeasibilityAlternative(
                type="adjust_target",
                current_target_amount=t,
                projected_target_amount=projected_value,
                description=f"Based on your current investment plan, this may be a more realistic target: ₹{projected_value:,.2f}."
            ))

            # D. Review Risk Profile (informational only)
            alternatives.append(GoalFeasibilityAlternative(
                type="review_risk_profile",
                description="A different risk profile may change expected return assumptions, but higher returns are not guaranteed and may involve higher volatility."
            ))

        goal_summary = {
            "target_amount": t,
            "current_amount": pv,
            "monthly_investment": p_planned,
            "horizon_months": horizon_months,
            "risk_level": risk
        }

        projection = {
            "projected_value": projected_value,
            "required_monthly_investment": p_required,
            "investment_gap": investment_gap
        }

        assumptions_data = {
            "expected_return": annual_rate,
            "return_type": "planning_estimate",
            "disclaimer": PLANNING_DISCLAIMER
        }

        return GoalFeasibilityPreviewResponse(
            status=status,
            reason=reason,
            goal_summary=goal_summary,
            projection=projection,
            assumptions=assumptions_data,
            alternatives=alternatives,
            next_step="review_alternatives" if alternatives else "proceed_to_strategy"
        )

    @staticmethod
    def apply_alternative(payload: GoalFeasibilityApplyRequest) -> GoalFeasibilityApplyResponse:
        """Applies a selected alternative strategy and returns a revised goal and strategy preview."""
        original = payload.original_goal
        alternative = payload.selected_alternative
        
        revised = GoalFeasibilityPreviewRequest(
            target_amount=original.target_amount,
            current_amount=original.current_amount,
            monthly_investment=original.monthly_investment,
            target_date=original.target_date,
            horizon_months=original.horizon_months,
            risk_level=original.risk_level
        )

        if alternative.type == "increase_monthly_investment" and alternative.recommended_monthly_investment is not None:
            revised.monthly_investment = alternative.recommended_monthly_investment
        elif alternative.type == "extend_horizon" and alternative.recommended_horizon_months is not None:
            revised.horizon_months = alternative.recommended_horizon_months
            if revised.target_date is not None:
                # Add calculated months to today's date
                revised.target_date = date.today() + relativedelta(months=alternative.recommended_horizon_months)
        elif alternative.type == "adjust_target" and alternative.projected_target_amount is not None:
            revised.target_amount = alternative.projected_target_amount

        # Re-evaluate feasibility for the revised goal
        revised_feasibility = FeasibilityService.calculate_feasibility(revised)

        # Generate a strategy preview based on revised values (using goals service logic)
        from app.modules.goals.service import GoalService
        from app.modules.goals.schemas import GoalStrategyPreviewRequest
        
        preview_req = GoalStrategyPreviewRequest(
            name="Revised Goal",
            target_amount=revised.target_amount,
            target_date=revised.target_date or (date.today() + relativedelta(months=revised.horizon_months) if revised.horizon_months else date.today()),
            risk_level=revised.risk_level,
            goal_type="custom",
            tax_profile=None
        )
        strategy_preview = GoalService.preview_strategy(preview_req)

        return GoalFeasibilityApplyResponse(
            status=revised_feasibility.status,
            revised_goal=revised,
            strategy_preview=strategy_preview
        )
