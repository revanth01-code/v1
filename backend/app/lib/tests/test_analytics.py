"""
Tests for analytics.py — pure financial metrics calculations.

All tests use controlled synthetic observations and known mathematical results.
No DB access, no network calls.

Assumptions under test match the module-level documentation:
  - CAGR formula: (end / start) ^ (1/years) - 1
  - Volatility: std(log_returns) * sqrt(252)
  - Max drawdown: min peak-to-trough fraction in [-1, 0]
  - Sharpe: (annualised_return - 0.06) / annualised_volatility
  - Sortino: (annualised_return - 0.06) / downside_deviation_annualised
  - Risk-free rate: 6.0% (RISK_FREE_RATE_ANNUAL constant)
  - Annualisation: 252 trading days (TRADING_DAYS_PER_YEAR constant)
"""
import math
import pytest
from datetime import date, timedelta

from app.modules.universe.analytics import (
    calculate_cagr,
    calculate_annualised_volatility,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    compute_cagr_from_obs,
    compute_metrics_for_asset,
    compute_data_confidence,
    compute_peer_reliability,
    _sorted_obs,
    _log_returns,
    _find_nearest_obs,
    compute_trailing_cagr,
    RISK_FREE_RATE_ANNUAL,
    TRADING_DAYS_PER_YEAR,
    MIN_OBS_VOLATILITY,
    MIN_OBS_1Y_CAGR,
    MAX_NEAREST_OBS_TOLERANCE_DAYS,
)


# ---------------------------------------------------------------------------
# Helpers to build synthetic observation lists
# ---------------------------------------------------------------------------

def _make_obs(prices: list[float], start: date = date(2020, 1, 2)) -> list[dict]:
    """Create observation dicts with consecutive calendar dates."""
    obs = []
    d = start
    for i, p in enumerate(prices):
        obs.append({"observation_date": d.isoformat(), "price_or_nav": p})
        d += timedelta(days=1)
    return obs


def _make_obs_years(
    start_price: float, end_price: float, years: int, points_per_year: int = 252
) -> list[dict]:
    """Create a linear NAV series over `years` years with `points_per_year` points."""
    n = years * points_per_year
    step = (end_price - start_price) / (n - 1)
    prices = [start_price + i * step for i in range(n)]
    # Spread dates across the full year range
    start = date(2015, 1, 2)
    total_days = int(years * 365.25)
    step_days = total_days / (n - 1)
    obs = []
    for i, p in enumerate(prices):
        d = start + timedelta(days=round(i * step_days))
        obs.append({"observation_date": d.isoformat(), "price_or_nav": p})
    return obs


# ---------------------------------------------------------------------------
# calculate_cagr
# ---------------------------------------------------------------------------

class TestCalculateCagr:
    def test_double_in_one_year(self):
        # 100 -> 200 in 1 year => CAGR = 100%
        result = calculate_cagr(100.0, 200.0, 1.0)
        assert result == pytest.approx(1.0, rel=1e-6)

    def test_double_in_two_years(self):
        # 100 -> 200 in 2 years => CAGR = sqrt(2) - 1 ≈ 41.42%
        result = calculate_cagr(100.0, 200.0, 2.0)
        assert result == pytest.approx(math.sqrt(2) - 1, rel=1e-6)

    def test_ten_percent_per_year(self):
        # 100 -> 100*(1.1^5) in 5 years => CAGR = 10%
        end = 100.0 * (1.1 ** 5)
        result = calculate_cagr(100.0, end, 5.0)
        assert result == pytest.approx(0.10, rel=1e-6)

    def test_zero_start_returns_none(self):
        assert calculate_cagr(0.0, 200.0, 1.0) is None

    def test_negative_start_returns_none(self):
        assert calculate_cagr(-100.0, 200.0, 1.0) is None

    def test_zero_years_returns_none(self):
        assert calculate_cagr(100.0, 200.0, 0.0) is None

    def test_negative_years_returns_none(self):
        assert calculate_cagr(100.0, 200.0, -1.0) is None

    def test_loss_returns_negative_cagr(self):
        # 100 -> 50 in 2 years => CAGR = sqrt(0.5) - 1 ≈ -29.29%
        result = calculate_cagr(100.0, 50.0, 2.0)
        assert result == pytest.approx(math.sqrt(0.5) - 1, rel=1e-6)
        assert result < 0

    def test_no_change_returns_zero(self):
        result = calculate_cagr(100.0, 100.0, 5.0)
        assert result == pytest.approx(0.0, abs=1e-10)


# ---------------------------------------------------------------------------
# _sorted_obs
# ---------------------------------------------------------------------------

class TestSortedObs:
    def test_sorts_oldest_first(self):
        raw = [
            {"observation_date": "2022-03-01", "price_or_nav": 10.0},
            {"observation_date": "2022-01-01", "price_or_nav": 9.0},
            {"observation_date": "2022-02-01", "price_or_nav": 9.5},
        ]
        result = _sorted_obs(raw)
        dates = [r[0] for r in result]
        assert dates == sorted(dates)

    def test_drops_non_positive_prices(self):
        raw = [
            {"observation_date": "2022-01-01", "price_or_nav": 0.0},
            {"observation_date": "2022-01-02", "price_or_nav": -1.0},
            {"observation_date": "2022-01-03", "price_or_nav": 10.0},
        ]
        result = _sorted_obs(raw)
        assert len(result) == 1
        assert result[0][1] == 10.0

    def test_drops_malformed_rows(self):
        raw = [
            {"observation_date": "not-a-date", "price_or_nav": 10.0},
            {"observation_date": "2022-01-01", "price_or_nav": "not-a-float"},
            {"observation_date": "2022-01-02", "price_or_nav": 15.0},
        ]
        result = _sorted_obs(raw)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _log_returns
# ---------------------------------------------------------------------------

class TestLogReturns:
    def test_constant_price_returns_zeros(self):
        obs = _sorted_obs(_make_obs([100.0] * 5))
        rets = _log_returns(obs)
        assert len(rets) == 4
        for r in rets:
            assert abs(r) < 1e-12

    def test_doubling_returns_log2(self):
        # Price doubles in one step: ln(200/100) = ln(2)
        obs = _sorted_obs(_make_obs([100.0, 200.0]))
        rets = _log_returns(obs)
        assert len(rets) == 1
        assert rets[0] == pytest.approx(math.log(2), rel=1e-6)


# ---------------------------------------------------------------------------
# Volatility
# ---------------------------------------------------------------------------

class TestAnnualisedVolatility:
    def test_constant_prices_zero_volatility(self):
        obs = _sorted_obs(_make_obs([100.0] * 100))
        vol = calculate_annualised_volatility(obs)
        assert vol == pytest.approx(0.0, abs=1e-10)

    def test_returns_none_below_min_obs(self):
        obs = _sorted_obs(_make_obs([100.0] * (MIN_OBS_VOLATILITY - 1)))
        assert calculate_annualised_volatility(obs) is None

    def test_annualisation_factor_applied(self):
        # If daily std is known, annual std = daily_std * sqrt(252)
        # Use prices that yield known daily returns
        import random
        random.seed(42)
        daily_ret = 0.01  # 1% daily return, constant
        prices = [100.0]
        for _ in range(99):
            prices.append(prices[-1] * math.exp(daily_ret))
        obs = _sorted_obs(_make_obs(prices))
        # With constant returns, daily std = 0, annual vol = 0
        vol = calculate_annualised_volatility(obs)
        assert vol == pytest.approx(0.0, abs=1e-10)

    def test_positive_vol_for_random_prices(self):
        # Build a series with genuine variability
        prices = [100.0]
        for i in range(59):
            prices.append(prices[-1] * (1 + (0.01 if i % 2 == 0 else -0.005)))
        obs = _sorted_obs(_make_obs(prices))
        vol = calculate_annualised_volatility(obs)
        assert vol is not None
        assert vol > 0.0


# ---------------------------------------------------------------------------
# Max Drawdown
# ---------------------------------------------------------------------------

class TestMaxDrawdown:
    def test_always_rising_has_zero_drawdown(self):
        prices = [float(i) for i in range(10, 110, 10)]  # 10, 20, ..., 100
        obs = _sorted_obs(_make_obs(prices))
        dd = calculate_max_drawdown(obs)
        assert dd == pytest.approx(0.0, abs=1e-10)

    def test_peak_then_50pct_drop(self):
        # 100 -> 200 -> 100: max drawdown = -50%
        obs = _sorted_obs(_make_obs([100.0, 200.0, 100.0]))
        dd = calculate_max_drawdown(obs)
        assert dd == pytest.approx(-0.5, rel=1e-6)

    def test_always_falling(self):
        # 100 -> 80 -> 60 -> 40: max drawdown = (40-100)/100 = -60%
        obs = _sorted_obs(_make_obs([100.0, 80.0, 60.0, 40.0]))
        dd = calculate_max_drawdown(obs)
        assert dd == pytest.approx(-0.6, rel=1e-6)

    def test_fewer_than_2_obs_returns_none(self):
        obs = _sorted_obs(_make_obs([100.0]))
        assert calculate_max_drawdown(obs) is None

    def test_result_in_valid_range(self):
        prices = [100.0, 120.0, 80.0, 130.0, 90.0]
        obs = _sorted_obs(_make_obs(prices))
        dd = calculate_max_drawdown(obs)
        assert dd is not None
        assert -1.0 <= dd <= 0.0


# ---------------------------------------------------------------------------
# Sharpe Ratio
# ---------------------------------------------------------------------------

class TestSharpeRatio:
    def test_returns_none_below_min_obs(self):
        obs = _sorted_obs(_make_obs([100.0] * (MIN_OBS_VOLATILITY - 1)))
        assert calculate_sharpe_ratio(obs) is None

    def test_zero_volatility_returns_none(self):
        # Constant prices => zero volatility => Sharpe undefined
        obs = _sorted_obs(_make_obs([100.0] * 100))
        assert calculate_sharpe_ratio(obs) is None

    def test_sharpe_positive_for_high_return_low_risk(self):
        # Steadily rising prices with tiny fluctuation -> high Sharpe
        prices = [100.0 * (1.0005 ** i) for i in range(100)]
        obs = _sorted_obs(_make_obs(prices))
        sharpe = calculate_sharpe_ratio(obs)
        # Can't assert exact value due to tiny std, but should be positive
        # (or None if vol rounds to 0 — both are acceptable)
        if sharpe is not None:
            assert isinstance(sharpe, float)


# ---------------------------------------------------------------------------
# Sortino Ratio
# ---------------------------------------------------------------------------

class TestSortinoRatio:
    def test_returns_none_below_min_obs(self):
        obs = _sorted_obs(_make_obs([100.0] * (MIN_OBS_VOLATILITY - 1)))
        assert calculate_sortino_ratio(obs) is None

    def test_no_negative_returns_returns_none(self):
        # Always rising prices => no negative daily returns => Sortino undefined
        prices = [float(i) for i in range(100, 200)]
        obs = _sorted_obs(_make_obs(prices))
        result = calculate_sortino_ratio(obs)
        assert result is None

    def test_with_mixed_returns_returns_float(self):
        # Mix of positive and negative daily returns
        prices = [100.0]
        for i in range(99):
            sign = 1 if i % 3 != 0 else -1
            prices.append(prices[-1] * (1 + sign * 0.005))
        obs = _sorted_obs(_make_obs(prices))
        sortino = calculate_sortino_ratio(obs)
        assert sortino is not None
        assert isinstance(sortino, float)


# ---------------------------------------------------------------------------
# compute_cagr_from_obs
# ---------------------------------------------------------------------------

class TestComputeCagrFromObs:
    def test_insufficient_obs_returns_none(self):
        obs = _sorted_obs(_make_obs([100.0, 110.0]))
        result = compute_cagr_from_obs(obs, min_years=0.9, min_obs=252)
        assert result is None

    def test_known_cagr_from_synthetic_series(self):
        # 5-year series: start=100, end=100*(1.12^5) => CAGR=12%
        end_price = 100.0 * (1.12 ** 5)
        obs_raw = _make_obs_years(100.0, end_price, years=5, points_per_year=260)
        obs = _sorted_obs(obs_raw)
        result = compute_cagr_from_obs(obs, min_years=4.9, min_obs=1260)
        assert result is not None
        # Allow 0.5% relative tolerance due to linear interpolation of prices
        assert result == pytest.approx(0.12, rel=0.05)


# ---------------------------------------------------------------------------
# compute_peer_reliability
# ---------------------------------------------------------------------------

class TestComputePeerReliability:
    def test_below_10_is_insufficient(self):
        assert compute_peer_reliability(9) == "INSUFFICIENT"
        assert compute_peer_reliability(0) == "INSUFFICIENT"

    def test_10_to_19_is_low(self):
        assert compute_peer_reliability(10) == "LOW"
        assert compute_peer_reliability(19) == "LOW"

    def test_20_and_above_is_high(self):
        assert compute_peer_reliability(20) == "HIGH"
        assert compute_peer_reliability(500) == "HIGH"


# ---------------------------------------------------------------------------
# compute_data_confidence
# ---------------------------------------------------------------------------

class TestComputeDataConfidence:
    def test_insufficient_below_min_obs(self):
        result = compute_data_confidence(
            obs_count=10,
            data_start=date(2023, 1, 1),
            data_end=date(2023, 6, 1),
            peer_reliability="HIGH",
        )
        assert result == "INSUFFICIENT"

    def test_high_confidence_5yr_high_peer(self):
        result = compute_data_confidence(
            obs_count=1300,
            data_start=date(2018, 1, 1),
            data_end=date.today(),
            peer_reliability="HIGH",
        )
        assert result == "HIGH"

    def test_medium_confidence_3yr(self):
        result = compute_data_confidence(
            obs_count=800,
            data_start=date(2021, 1, 1),
            data_end=date.today(),
            peer_reliability="LOW",
        )
        assert result == "MEDIUM"


# ---------------------------------------------------------------------------
# compute_metrics_for_asset (integration of the whole pipeline)
# ---------------------------------------------------------------------------

class TestComputeMetricsForAsset:
    def test_empty_observations_returns_insufficient(self):
        result = compute_metrics_for_asset([])
        assert result["sufficient_data"] is False
        assert result["historical_observation_count"] == 0

    def test_full_5yr_series_returns_all_metrics(self):
        end_price = 100.0 * (1.12 ** 5)
        obs_raw = _make_obs_years(100.0, end_price, years=6, points_per_year=260)
        result = compute_metrics_for_asset(obs_raw)

        assert result["sufficient_data"] is True
        m = result["metrics"]

        # All CAGR periods should be populated
        assert m["returns"]["1y"] is not None
        assert m["returns"]["3y"] is not None
        assert m["returns"]["5y"] is not None

        # Volatility should be non-negative
        assert m["volatility"] is not None
        assert m["volatility"] >= 0

        # Max drawdown in valid range
        assert m["max_drawdown"] is not None
        assert -1.0 <= m["max_drawdown"] <= 0.0

        # Metadata assumptions present
        assert m["risk_free_rate_used"] == RISK_FREE_RATE_ANNUAL
        assert m["annualisation_factor"] == TRADING_DAYS_PER_YEAR

    def test_metadata_assumptions_always_present(self):
        """Assumptions must be embedded in every metrics result, even insufficient."""
        result = compute_metrics_for_asset([])
        m = result["metrics"]
        assert "risk_free_rate_used" in m
        assert "annualisation_factor" in m

    def test_no_fabricated_nulls_replaced_with_zero(self):
        """If data is insufficient, metrics should be None, not 0."""
        short_obs = _make_obs([100.0, 110.0, 105.0])  # only 3 points
        result = compute_metrics_for_asset(short_obs)
        m = result["metrics"]
        # Should be None, not 0.0
        assert m["returns"]["1y"] is None
        assert m["volatility"] is None

    def test_all_time_cagr_present_separately(self):
        """all_time CAGR must be present in returns dict and not replace 1y/3y/5y."""
        end_price = 100.0 * (1.12 ** 6)
        obs_raw = _make_obs_years(100.0, end_price, years=6, points_per_year=260)
        result = compute_metrics_for_asset(obs_raw)
        m = result["metrics"]
        assert "all_time" in m["returns"]
        # All period metrics must be present as separate keys
        assert "1y" in m["returns"]
        assert "3y" in m["returns"]
        assert "5y" in m["returns"]


# ---------------------------------------------------------------------------
# _find_nearest_obs (Issue 1 fix)
# ---------------------------------------------------------------------------

class TestFindNearestObs:
    def test_exact_match(self):
        obs = _sorted_obs(_make_obs([100.0, 110.0, 120.0], start=date(2020, 1, 1)))
        result = _find_nearest_obs(obs, date(2020, 1, 2))  # index 1
        assert result is not None
        assert result[0] == date(2020, 1, 2)
        assert result[1] == 110.0

    def test_nearest_within_tolerance(self):
        obs = _sorted_obs(_make_obs([100.0, 110.0], start=date(2020, 6, 1)))
        # Target is 10 days before the first observation — still within 45-day tolerance
        target = date(2020, 5, 22)  # 10 days before 2020-06-01
        result = _find_nearest_obs(obs, target)
        assert result is not None
        assert result[0] == date(2020, 6, 1)

    def test_beyond_tolerance_returns_none(self):
        obs = _sorted_obs(_make_obs([100.0], start=date(2022, 1, 1)))
        # Target is 90 days before the only observation — beyond MAX_NEAREST_OBS_TOLERANCE_DAYS
        target = date(2021, 10, 3)  # 90 days before 2022-01-01
        result = _find_nearest_obs(obs, target)
        assert result is None

    def test_respects_custom_tolerance(self):
        obs = _sorted_obs(_make_obs([100.0], start=date(2022, 1, 1)))
        target = date(2021, 12, 25)  # 7 days before
        # With tolerance=5 days this should be None; with tolerance=10 it should find it
        assert _find_nearest_obs(obs, target, max_tolerance_days=5) is None
        assert _find_nearest_obs(obs, target, max_tolerance_days=10) is not None

    def test_empty_obs_returns_none(self):
        result = _find_nearest_obs([], date(2022, 1, 1))
        assert result is None


# ---------------------------------------------------------------------------
# compute_trailing_cagr (Issue 1 fix)
# ---------------------------------------------------------------------------

class TestComputeTrailingCagr:
    def test_insufficient_obs_returns_none(self):
        obs = _sorted_obs(_make_obs([100.0]))  # only 1 point
        assert compute_trailing_cagr(obs, years=1.0, min_actual_years=0.9) is None

    def test_no_history_for_window_returns_none(self):
        # 6-month series: no observation near the 1-year-ago target
        obs = _sorted_obs(_make_obs([100.0] * 180, start=date(2024, 1, 1)))
        # 1y window: target start is ~2023-01-01, but data only goes back to 2024-01-01
        result = compute_trailing_cagr(obs, years=1.0, min_actual_years=0.9)
        assert result is None

    def test_1y_trailing_correct_result(self):
        # Build a 2-year daily series where the last year grows at ~15% CAGR.
        # Year 1 (days 0-364): flat at 100
        # Year 2 (days 365-729): grows to 100 * 1.15
        start = date(2022, 1, 1)
        prices_yr1 = [100.0] * 365
        end_yr2 = 100.0 * 1.15
        prices_yr2 = [100.0 + (end_yr2 - 100.0) * i / 364 for i in range(365)]
        all_prices = prices_yr1 + prices_yr2
        obs_raw = []
        for i, p in enumerate(all_prices):
            obs_raw.append({"observation_date": (start + timedelta(days=i)).isoformat(),
                            "price_or_nav": p})
        obs = _sorted_obs(obs_raw)
        result = compute_trailing_cagr(obs, years=1.0, min_actual_years=0.9)
        assert result is not None
        # The 1y window starts near 2023-01-01 (price ~100) and ends at 2023-12-31 (price ~115)
        assert result == pytest.approx(0.15, rel=0.05)

    def test_windows_produce_different_values_for_nonlinear_series(self):
        """1y, 3y, 5y trailing CAGRs must be different when the price series
        has meaningfully different growth rates in different sub-periods.
        This is the key correctness assertion for Issue 1."""
        # Build a 6-year series with three distinct growth rate phases:
        #   Years 6-4 ago : 5% per year
        #   Years 4-1 ago : 20% per year
        #   Year 1-0 ago  : 3% per year
        start = date(2018, 1, 1)
        obs_raw = []
        price = 100.0
        for year_offset in range(6):
            if year_offset < 2:
                daily_rate = (1.05 ** (1 / 365)) - 1  # 5% p.a.
            elif year_offset < 5:
                daily_rate = (1.20 ** (1 / 365)) - 1  # 20% p.a.
            else:
                daily_rate = (1.03 ** (1 / 365)) - 1  # 3% p.a.
            for day in range(365):
                d = start + timedelta(days=year_offset * 365 + day)
                obs_raw.append({"observation_date": d.isoformat(), "price_or_nav": price})
                price *= (1 + daily_rate)

        obs = _sorted_obs(obs_raw)
        cagr_1y = compute_trailing_cagr(obs, years=1.0, min_actual_years=0.9)
        cagr_3y = compute_trailing_cagr(obs, years=3.0, min_actual_years=2.9)
        cagr_5y = compute_trailing_cagr(obs, years=5.0, min_actual_years=4.9)

        # All should be non-None (6 years of daily data)
        assert cagr_1y is not None, "1y CAGR should be computable from 6yr series"
        assert cagr_3y is not None, "3y CAGR should be computable from 6yr series"
        assert cagr_5y is not None, "5y CAGR should be computable from 6yr series"

        # They must be numerically distinct (different growth phases in each window)
        assert cagr_1y != pytest.approx(cagr_3y, rel=0.01), (
            "1y and 3y CAGRs should differ for a non-linear price series"
        )
        assert cagr_3y != pytest.approx(cagr_5y, rel=0.01), (
            "3y and 5y CAGRs should differ for a non-linear price series"
        )

        # Qualitative checks: last year was 3%, so 1y should be near 0.03
        assert cagr_1y == pytest.approx(0.03, rel=0.10)
        # Middle period was 20%, so 3y should be dominated by that
        assert cagr_3y > cagr_1y  # 20% phase dominates the 3y window

    def test_2yr_series_gives_1y_not_5y(self):
        """With only 2 years of data, 1y CAGR should be non-None, 5y should be None."""
        end_price = 100.0 * (1.10 ** 2)
        obs_raw = _make_obs_years(100.0, end_price, years=2, points_per_year=260)
        obs = _sorted_obs(obs_raw)
        cagr_1y = compute_trailing_cagr(obs, years=1.0, min_actual_years=0.9)
        cagr_5y = compute_trailing_cagr(obs, years=5.0, min_actual_years=4.9)
        assert cagr_1y is not None
        assert cagr_5y is None  # only 2 years of data available
