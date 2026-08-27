"""
analytics.py — Pure financial metrics calculations.

No I/O, no database access, no side effects.
Every function is independently unit-testable.

Assumptions (explicitly documented):
  - Observation frequency: daily (calendar days, not trading days).
    MFAPI returns calendar-day NAVs for Indian mutual funds, skipping
    non-trading days. We use calendar-day fractions for CAGR but
    annualise volatility using a 252 trading-day factor because
    Indian mutual fund industry convention treats 252 as the standard
    trading-year length.
  - Risk-free rate: 6.0% annualised (approximate Indian 91-day T-bill
    proxy). Stored as a module constant so callers can see it clearly.
  - Minimum history required for each metric:
      1y CAGR      : >= 252 calendar observations  (~1 trading year)
      3y CAGR      : >= 756 calendar observations
      5y CAGR      : >= 1260 calendar observations
      Volatility   : >= 30 observations (to compute meaningful std-dev)
      Max drawdown : >= 2 observations
      Sharpe/Sortino: requires valid volatility AND >= 30 obs
  - Trailing CAGR windows (1y/3y/5y): each measures returns over the
    most recent N calendar years ending at the latest observation date.
    The start price is taken from the nearest available observation to
    (data_end - N years), within MAX_NEAREST_OBS_TOLERANCE_DAYS (45 days).
    If no observation falls within tolerance the metric is null.
  - CAGR uses actual elapsed years between the found observations —
    no magic numbers.
  - Returns are computed as log-returns for volatility/Sharpe/Sortino
    but as simple price ratios for CAGR (standard convention).
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# Module-level constants (clearly documented, not magic numbers)
# ---------------------------------------------------------------------------

# Annualisation factor for volatility.
# Convention: 252 trading days per year (Indian mutual fund industry standard).
TRADING_DAYS_PER_YEAR: int = 252

# Risk-free rate used for Sharpe / Sortino calculations.
# Approximate Indian 91-day T-bill yield (annualised). This is an assumption,
# not a live feed. Clearly labelled so consumers can substitute their own value.
RISK_FREE_RATE_ANNUAL: float = 0.06  # 6.0% per annum

# Minimum observations required to compute each metric.
MIN_OBS_VOLATILITY: int = 30       # std-dev is meaningless below ~30 points
MIN_OBS_1Y_CAGR: int = 252         # ~1 trading year of daily NAVs
MIN_OBS_3Y_CAGR: int = 756         # ~3 trading years
MIN_OBS_5Y_CAGR: int = 1260        # ~5 trading years
MIN_OBS_DRAWDOWN: int = 2          # need at least a peak and a trough

# Elapsed-year thresholds for CAGR guarding (calendar time, not obs count).
MIN_YEARS_1Y: float = 0.9          # allow a 10% tolerance for 1-year
MIN_YEARS_3Y: float = 2.9
MIN_YEARS_5Y: float = 4.9

# Maximum calendar days the nearest-observation search will tolerate when
# finding the start of a trailing CAGR window. 45 days covers weekends,
# Indian market holidays, and minor data gaps without fabricating a start point.
MAX_NEAREST_OBS_TOLERANCE_DAYS: int = 45


# ---------------------------------------------------------------------------
# Core helper: sort and validate observation list
# ---------------------------------------------------------------------------

ObsPoint = tuple[date, float]  # (observation_date, price_or_nav)


def _sorted_obs(observations: list[dict]) -> list[ObsPoint]:
    """Convert raw dicts to sorted (date, price) tuples.

    Input dicts must have keys:
        observation_date: str  "YYYY-MM-DD"
        price_or_nav:     float | str

    Rows with missing or non-positive prices are silently dropped.
    Returned list is sorted oldest → newest.
    """
    pts: list[ObsPoint] = []
    for row in observations:
        try:
            d = date.fromisoformat(str(row["observation_date"]))
            p = float(row["price_or_nav"])
            if p > 0:
                pts.append((d, p))
        except (KeyError, ValueError, TypeError):
            continue
    pts.sort(key=lambda x: x[0])
    return pts


def _elapsed_years(start: date, end: date) -> float:
    """Fractional years between two dates using actual calendar days."""
    return (end - start).days / 365.25


# ---------------------------------------------------------------------------
# CAGR
# ---------------------------------------------------------------------------

def calculate_cagr(
    start_price: float, end_price: float, years: float
) -> Optional[float]:
    """Compound Annual Growth Rate.

    Formula: (end_price / start_price) ^ (1 / years) - 1

    Returns None if mathematically invalid (non-positive prices,
    non-positive years, or prices lead to a complex root for negative
    start-to-end values — e.g. structured products with negative NAV
    changes are correctly returned as negative).

    Note: CAGR for a fund that lost money will be negative, which is
    mathematically valid and correctly returned.
    """
    if start_price <= 0 or end_price <= 0 or years <= 0:
        return None
    ratio = end_price / start_price
    if ratio <= 0:
        return None
    return (ratio ** (1.0 / years)) - 1.0


def compute_cagr_from_obs(
    obs: list[ObsPoint], min_years: float, min_obs: int
) -> Optional[float]:
    """Compute full-series CAGR from a sorted observation list.

    Uses the first and last observation (entire available history).
    This is stored as 'all_time' in the metrics JSON and must NOT
    be confused with the trailing 1y/3y/5y window CAGRs.

    Guards:
      - Must have >= min_obs observations.
      - Elapsed calendar years must be >= min_years.

    Returns the CAGR as a decimal fraction (e.g. 0.1234 = 12.34%),
    or None if guards are not met.
    """
    if len(obs) < min_obs:
        return None
    years = _elapsed_years(obs[0][0], obs[-1][0])
    if years < min_years:
        return None
    return calculate_cagr(obs[0][1], obs[-1][1], years)


# ---------------------------------------------------------------------------
# Trailing-window CAGR (Issue 1 fix)
# ---------------------------------------------------------------------------

def _find_nearest_obs(
    obs: list[ObsPoint],
    target_date: date,
    max_tolerance_days: int = MAX_NEAREST_OBS_TOLERANCE_DAYS,
) -> Optional[ObsPoint]:
    """Return the observation closest to target_date within max_tolerance_days.

    Binary-search would be faster for large lists, but mutual fund NAV
    histories are at most ~8,000 points and a linear scan is negligible.
    Returns None if the nearest observation exceeds max_tolerance_days.
    """
    best: Optional[ObsPoint] = None
    best_delta = max_tolerance_days + 1  # start above tolerance
    for pt in obs:
        delta = abs((pt[0] - target_date).days)
        if delta < best_delta:
            best_delta = delta
            best = pt
    return best if best_delta <= max_tolerance_days else None


def compute_trailing_cagr(
    obs: list[ObsPoint],
    years: float,
    min_actual_years: float,
) -> Optional[float]:
    """Compute CAGR for the trailing `years` period ending at the last observation.

    The start of the window is the nearest available observation to
    (data_end - years * 365.25 days), within MAX_NEAREST_OBS_TOLERANCE_DAYS.

    Args:
        obs             : Sorted list of (date, price) tuples, oldest first.
        years           : Target trailing window in years (e.g. 1.0, 3.0, 5.0).
        min_actual_years: Minimum actual elapsed years required between the
                          found start observation and the end observation.
                          Prevents e.g. a 3y window being satisfied by 2.5y
                          of data when the start observation falls near the
                          edge of the tolerance band.

    Returns the CAGR as a decimal fraction, or None if:
      - Fewer than 2 observations.
      - No observation falls within MAX_NEAREST_OBS_TOLERANCE_DAYS of target.
      - Actual elapsed years between found start and end < min_actual_years.
    """
    if len(obs) < 2:
        return None

    end_pt = obs[-1]
    target_start_date = end_pt[0] - timedelta(days=round(years * 365.25))

    start_pt = _find_nearest_obs(obs, target_start_date)
    if start_pt is None:
        return None

    # Guard: the found start observation must not be the same as the end point
    if start_pt[0] >= end_pt[0]:
        return None

    actual_years = _elapsed_years(start_pt[0], end_pt[0])
    if actual_years < min_actual_years:
        return None

    return calculate_cagr(start_pt[1], end_pt[1], actual_years)


# ---------------------------------------------------------------------------
# Log-returns (used for volatility, Sharpe, Sortino)
# ---------------------------------------------------------------------------

def _log_returns(obs: list[ObsPoint]) -> list[float]:
    """Daily log-returns: ln(P_t / P_{t-1}).

    Log-returns are used (rather than simple returns) because they are
    time-additive, which simplifies annualisation.
    """
    rets: list[float] = []
    for i in range(1, len(obs)):
        prev = obs[i - 1][1]
        curr = obs[i][1]
        if prev > 0 and curr > 0:
            rets.append(math.log(curr / prev))
    return rets


# ---------------------------------------------------------------------------
# Annualised Volatility
# ---------------------------------------------------------------------------

def calculate_annualised_volatility(obs: list[ObsPoint]) -> Optional[float]:
    """Standard deviation of daily log-returns, annualised.

    Annualisation: sigma_annual = sigma_daily * sqrt(252)
    (252 = TRADING_DAYS_PER_YEAR — see module docstring assumption.)

    Returns None if fewer than MIN_OBS_VOLATILITY observations exist.
    """
    if len(obs) < MIN_OBS_VOLATILITY:
        return None
    rets = _log_returns(obs)
    if len(rets) < MIN_OBS_VOLATILITY - 1:
        return None

    n = len(rets)
    mean = sum(rets) / n
    variance = sum((r - mean) ** 2 for r in rets) / (n - 1)  # sample variance
    daily_std = math.sqrt(variance)
    return daily_std * math.sqrt(TRADING_DAYS_PER_YEAR)


# ---------------------------------------------------------------------------
# Maximum Drawdown
# ---------------------------------------------------------------------------

def calculate_max_drawdown(obs: list[ObsPoint]) -> Optional[float]:
    """Maximum peak-to-trough decline as a fraction (negative value).

    Formula: min over t of (price_t - running_peak_t) / running_peak_t

    Returns a value in [-1, 0] where -1 means total loss.
    Returns None if fewer than MIN_OBS_DRAWDOWN observations.

    Example: max_drawdown = -0.35 means the fund fell 35% from its peak.
    """
    if len(obs) < MIN_OBS_DRAWDOWN:
        return None

    peak = obs[0][1]
    max_dd = 0.0
    for _, price in obs:
        if price > peak:
            peak = price
        dd = (price - peak) / peak
        if dd < max_dd:
            max_dd = dd
    return max_dd


# ---------------------------------------------------------------------------
# Sharpe Ratio
# ---------------------------------------------------------------------------

def calculate_sharpe_ratio(
    obs: list[ObsPoint],
    annualised_volatility: Optional[float] = None,
) -> Optional[float]:
    """Annualised Sharpe ratio using daily log-returns.

    Sharpe = (annualised_return - risk_free_rate) / annualised_volatility

    Where:
      annualised_return  = mean(daily_log_returns) * 252
      annualised_volatility = std(daily_log_returns) * sqrt(252)
      risk_free_rate     = RISK_FREE_RATE_ANNUAL (6% — see module constant)

    Returns None if:
      - Fewer than MIN_OBS_VOLATILITY observations.
      - Annualised volatility is zero or very near zero (undefined ratio).
    """
    if len(obs) < MIN_OBS_VOLATILITY:
        return None

    rets = _log_returns(obs)
    if len(rets) < MIN_OBS_VOLATILITY - 1:
        return None

    # Compute volatility if not pre-computed
    if annualised_volatility is None:
        vol = calculate_annualised_volatility(obs)
    else:
        vol = annualised_volatility

    if vol is None or vol < 1e-10:
        return None  # undefined or division by near-zero

    n = len(rets)
    mean_daily = sum(rets) / n
    annualised_return = mean_daily * TRADING_DAYS_PER_YEAR
    return (annualised_return - RISK_FREE_RATE_ANNUAL) / vol


# ---------------------------------------------------------------------------
# Sortino Ratio
# ---------------------------------------------------------------------------

def calculate_sortino_ratio(
    obs: list[ObsPoint],
) -> Optional[float]:
    """Annualised Sortino ratio using daily log-returns.

    Sortino = (annualised_return - risk_free_rate) / downside_deviation

    Where downside deviation uses only returns below zero (not below the
    risk-free rate, which is the simplified but widely-used convention for
    daily data):
      downside_deviation = sqrt(mean(min(r, 0)^2)) * sqrt(252)

    Returns None if:
      - Fewer than MIN_OBS_VOLATILITY observations.
      - No negative daily returns exist (downside deviation = 0).
    """
    if len(obs) < MIN_OBS_VOLATILITY:
        return None

    rets = _log_returns(obs)
    if len(rets) < MIN_OBS_VOLATILITY - 1:
        return None

    n = len(rets)
    mean_daily = sum(rets) / n
    annualised_return = mean_daily * TRADING_DAYS_PER_YEAR

    # Downside returns (below zero)
    neg_rets = [r for r in rets if r < 0]
    if not neg_rets:
        return None  # no downside — ratio undefined

    downside_variance = sum(r ** 2 for r in neg_rets) / n  # semi-variance
    downside_std_daily = math.sqrt(downside_variance)
    downside_std_annual = downside_std_daily * math.sqrt(TRADING_DAYS_PER_YEAR)

    if downside_std_annual < 1e-10:
        return None

    return (annualised_return - RISK_FREE_RATE_ANNUAL) / downside_std_annual


# ---------------------------------------------------------------------------
# Data Confidence
# ---------------------------------------------------------------------------

def compute_data_confidence(
    obs_count: int,
    data_start: date,
    data_end: date,
    peer_reliability: str,
) -> str:
    """Classify data confidence level.

    HIGH   : >= ~5 years of usable history + recent data + HIGH peer reliability
    MEDIUM : >= ~3 years of usable history with acceptable freshness
    LOW    : < 3 years history or stale data
    INSUFFICIENT: very limited observations or mathematically insufficient
    """
    if obs_count < MIN_OBS_VOLATILITY:
        return "INSUFFICIENT"

    years = _elapsed_years(data_start, data_end)
    days_since_update = (date.today() - data_end).days

    if years >= 4.9 and days_since_update <= 14 and peer_reliability == "HIGH":
        return "HIGH"
    elif years >= 2.9 and days_since_update <= 30:
        return "MEDIUM"
    elif years >= 0.9:
        return "LOW"
    else:
        return "INSUFFICIENT"


# ---------------------------------------------------------------------------
# Peer Reliability
# ---------------------------------------------------------------------------

def compute_peer_reliability(peer_count: int) -> str:
    """Classify peer group reliability.

    INSUFFICIENT : peer_count < 10
    LOW          : peer_count 10–19
    HIGH         : peer_count >= 20
    """
    if peer_count < 10:
        return "INSUFFICIENT"
    elif peer_count < 20:
        return "LOW"
    else:
        return "HIGH"


# ---------------------------------------------------------------------------
# Top-level: compute all metrics for one asset
# ---------------------------------------------------------------------------

def compute_metrics_for_asset(
    observations: list[dict],
) -> dict:
    """Compute all metrics for one asset from its raw observation records.

    Input:
        observations: list of dicts with keys:
            observation_date  (str "YYYY-MM-DD")
            price_or_nav      (float or str)

    Returns a dict with:
        metrics               : structured dict matching asset_metrics.metrics JSONB schema
        data_start_date       : str | None
        data_end_date         : str | None
        historical_observation_count : int
        sufficient_data       : bool  — False means INSUFFICIENT and caller
                                        may choose to skip storing or to store
                                        an INSUFFICIENT record.

    This function never raises. All failures are captured as None values.
    """
    obs = _sorted_obs(observations)
    n = len(obs)

    if n < MIN_OBS_DRAWDOWN:
        return {
            "metrics": {
                "returns": {"1y": None, "3y": None, "5y": None},
                "volatility": None,
                "max_drawdown": None,
                "sharpe_ratio": None,
                "sortino_ratio": None,
                "risk_free_rate_used": RISK_FREE_RATE_ANNUAL,
                "annualisation_factor": TRADING_DAYS_PER_YEAR,
            },
            "data_start_date": None,
            "data_end_date": None,
            "historical_observation_count": n,
            "sufficient_data": False,
        }

    data_start = obs[0][0]
    data_end = obs[-1][0]

    # Compute volatility once; reuse it in Sharpe
    vol = calculate_annualised_volatility(obs)

    metrics = {
        "returns": {
            # Trailing-period CAGRs: window ends at data_end_date.
            # Start is the nearest observation to (data_end - N years),
            # within 45 calendar days. Null if insufficient history.
            "1y": compute_trailing_cagr(obs, years=1.0, min_actual_years=MIN_YEARS_1Y),
            "3y": compute_trailing_cagr(obs, years=3.0, min_actual_years=MIN_YEARS_3Y),
            "5y": compute_trailing_cagr(obs, years=5.0, min_actual_years=MIN_YEARS_5Y),
            # Full-series CAGR from earliest to latest observation.
            # Stored separately for reference; does NOT replace the period metrics.
            "all_time": compute_cagr_from_obs(obs, MIN_YEARS_1Y, 2),
        },
        "volatility": vol,
        "max_drawdown": calculate_max_drawdown(obs),
        "sharpe_ratio": calculate_sharpe_ratio(obs, annualised_volatility=vol),
        "sortino_ratio": calculate_sortino_ratio(obs),
        # Clearly document the assumptions embedded in the computed values
        "risk_free_rate_used": RISK_FREE_RATE_ANNUAL,
        "annualisation_factor": TRADING_DAYS_PER_YEAR,
    }

    sufficient_data = n >= MIN_OBS_VOLATILITY

    return {
        "metrics": metrics,
        "data_start_date": data_start.isoformat(),
        "data_end_date": data_end.isoformat(),
        "historical_observation_count": n,
        "sufficient_data": sufficient_data,
    }
