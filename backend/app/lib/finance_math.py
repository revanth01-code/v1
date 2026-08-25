"""Pure financial math — no I/O, no DB, no side effects. Every function here
is independently unit-testable and used by the feasibility engine (and later
by goals/retirement/emergency_fund) rather than duplicated per module.

Convention: SIP contributions are modeled as an annuity due (invested at the
START of each month) — this matches how Indian SIP calculators typically
compute future value, and is intentionally consistent across every caller.
"""


def calculate_future_value_of_contribution(
    monthly_contribution: float, months: int, annual_return_pct: float
) -> float:
    """Future value of a monthly SIP contribution over `months` months."""
    if months <= 0 or monthly_contribution <= 0:
        return 0.0

    r = annual_return_pct / 12 / 100
    if r == 0:
        return monthly_contribution * months

    return monthly_contribution * (((1 + r) ** months - 1) / r) * (1 + r)


def calculate_lumpsum_future_value(
    present_value: float, years: float, annual_return_pct: float
) -> float:
    """Future value of a one-time lumpsum investment over `years` years."""
    if years <= 0 or present_value <= 0:
        return present_value

    r = annual_return_pct / 100
    return present_value * ((1 + r) ** years)


def calculate_required_sip(target_amount: float, months: int, annual_return_pct: float) -> float:
    """Monthly SIP required to reach `target_amount` in `months` months."""
    if months <= 0:
        raise ValueError("months must be positive")
    if target_amount <= 0:
        return 0.0

    r = annual_return_pct / 12 / 100
    if r == 0:
        return target_amount / months

    factor = (((1 + r) ** months - 1) / r) * (1 + r)
    return target_amount / factor


def inflation_adjusted_target(present_value: float, years: float, inflation_pct: float) -> float:
    """What a present-day target amount will cost `years` from now, given
    `inflation_pct` annual inflation."""
    if years <= 0:
        return present_value
    return present_value * ((1 + inflation_pct / 100) ** years)

def calculate_growing_annuity_pv(
    first_payment: float, periods: int, rate_pct: float, growth_pct: float
) -> float:
    """Present value (as of the start of the annuity) of a series of
    payments that grow each period — used for retirement corpus sizing,
    where withdrawals must grow with inflation each year to maintain
    purchasing power, while the remaining corpus keeps earning returns.
    `first_payment` is the amount needed in period 1 (already inflation
    -adjusted to the retirement date)."""
    if periods <= 0 or first_payment <= 0:
        return 0.0

    r = rate_pct / 100
    g = growth_pct / 100

    if abs(r - g) < 1e-9:
        # degenerate case: return rate equals growth rate
        return first_payment * periods / (1 + r)

    return first_payment * (1 - ((1 + g) / (1 + r)) ** periods) / (r - g)