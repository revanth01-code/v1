from datetime import date
from app.lib.date_utils import months_between
from app.lib.finance_math import (
    calculate_future_value_of_contribution,
    calculate_lumpsum_future_value,
    calculate_required_sip,
    inflation_adjusted_target,
)
from .schemas import FeasibilityInput, FeasibilityResult

BORDERLINE_THRESHOLD = 0.85  # within 15% of target counts as "borderline"
MAX_SEARCH_MONTHS = 600  # cap the extended-duration search at 50 years


def _project_value(
    months: int,
    monthly_contribution: float,
    lumpsum_amount: float,
    expected_return_pct: float,
) -> float:
    sip_fv = calculate_future_value_of_contribution(monthly_contribution, months, expected_return_pct)
    lumpsum_fv = calculate_lumpsum_future_value(lumpsum_amount, months / 12, expected_return_pct)
    return sip_fv + lumpsum_fv


def _find_required_months(
    monthly_contribution: float,
    lumpsum_amount: float,
    expected_return_pct: float,
    inflation_pct: float,
    present_target: float,
) -> int | None:
    """Searches month-by-month for how long it would take the CURRENT
    contribution plan to reach the (inflation-adjusted-for-that-duration)
    target. Returns None if not reachable within MAX_SEARCH_MONTHS — this
    can genuinely happen with zero/near-zero contributions."""
    for months in range(1, MAX_SEARCH_MONTHS + 1):
        years = months / 12
        adjusted_target = inflation_adjusted_target(present_target, years, inflation_pct)
        projected = _project_value(months, monthly_contribution, lumpsum_amount, expected_return_pct)
        if projected >= adjusted_target:
            return months
    return None


class FeasibilityEngine:
    @staticmethod
    def check(input: FeasibilityInput) -> FeasibilityResult:
        start = input.start_date or date.today()
        months = months_between(start, input.target_date)
        years = months / 12

        adjusted_target = inflation_adjusted_target(input.target_amount, years, input.inflation_pct)
        projected_value = _project_value(
            months, input.monthly_contribution, input.lumpsum_amount, input.expected_return_pct
        )

        ratio = projected_value / adjusted_target if adjusted_target > 0 else 1.0
        shortfall = max(adjusted_target - projected_value, 0.0)

        # How much lumpsum alone is expected to grow to by the target date —
        # subtracting this from the target tells us what the SIP alone still
        # needs to cover.
        lumpsum_fv = calculate_lumpsum_future_value(input.lumpsum_amount, years, input.expected_return_pct)
        remaining_for_sip = max(adjusted_target - lumpsum_fv, 0)
        suggested_sip = (
            round(calculate_required_sip(remaining_for_sip, months, input.expected_return_pct), 2)
            if months > 0
            else None
        )

        contrib_diff = max((suggested_sip or 0.0) - input.monthly_contribution, 0.0) if suggested_sip is not None else 0.0

        suggested_extended_months = _find_required_months(
            input.monthly_contribution,
            input.lumpsum_amount,
            input.expected_return_pct,
            input.inflation_pct,
            input.target_amount,
        )

        if ratio >= 1.15:
            status = "highly_feasible"
            message = "Your plan is in excellent shape! The projected corpus is expected to comfortably exceed your inflation-adjusted target."
        elif ratio >= 1.0:
            status = "feasible"
            message = "Your plan is on track! The projected corpus meets your inflation-adjusted target based on your current inputs."
        elif ratio >= 0.85:
            status = "borderline"
            message = "You're close — a small increase in your monthly contribution would get this goal fully on track."
        elif ratio >= 0.5:
            status = "at_risk"
            message = "Your goal is currently At Risk because the inflation-adjusted target is significantly higher than the projected corpus under your current contribution."
        else:
            status = "unlikely"
            message = "Your goal is currently Unlikely to be met. The projected corpus is less than half of your target. Consider extending your timeline, adding a lumpsum, or increasing your SIP."

        return FeasibilityResult(
            status=status,
            months=months,
            inflation_adjusted_target=round(adjusted_target, 2),
            projected_value=round(projected_value, 2),
            shortfall=round(shortfall, 2),
            suggested_monthly_sip=suggested_sip,
            contribution_difference=round(contrib_diff, 2),
            suggested_extended_months=suggested_extended_months,
            message=message,
        )