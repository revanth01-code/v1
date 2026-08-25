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

        if projected_value >= adjusted_target:
            return FeasibilityResult(
                status="feasible",
                months=months,
                inflation_adjusted_target=round(adjusted_target, 2),
                projected_value=round(projected_value, 2),
            )

        shortfall = adjusted_target - projected_value

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

        suggested_extended_months = _find_required_months(
            input.monthly_contribution,
            input.lumpsum_amount,
            input.expected_return_pct,
            input.inflation_pct,
            input.target_amount,
        )

        if projected_value >= adjusted_target * BORDERLINE_THRESHOLD:
            status = "borderline"
            message = (
                "You're close — a small increase in your monthly contribution "
                "would get this goal fully on track."
            )
        else:
            status = "infeasible"
            message = (
                "This goal isn't on track with your current plan. "
                "Increase your monthly SIP, extend your timeline, or reconsider the target amount."
            )

        return FeasibilityResult(
            status=status,
            months=months,
            inflation_adjusted_target=round(adjusted_target, 2),
            projected_value=round(projected_value, 2),
            shortfall=round(shortfall, 2),
            suggested_monthly_sip=suggested_sip,
            suggested_extended_months=suggested_extended_months,
            message=message,
        )