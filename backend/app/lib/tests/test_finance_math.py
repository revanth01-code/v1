import pytest
from app.lib.finance_math import (
    calculate_future_value_of_contribution,
    calculate_growing_annuity_pv,
    calculate_lumpsum_future_value,
    calculate_required_sip,
    inflation_adjusted_target,
)


class TestFutureValueOfContribution:
    def test_zero_months_returns_zero(self):
        assert calculate_future_value_of_contribution(5000, 0, 12) == 0

    def test_zero_contribution_returns_zero(self):
        assert calculate_future_value_of_contribution(0, 12, 12) == 0

    def test_zero_return_is_simple_sum(self):
        assert calculate_future_value_of_contribution(1000, 12, 0) == 12000

    def test_grows_with_positive_return(self):
        fv = calculate_future_value_of_contribution(5000, 120, 12)
        # 5000/month for 10 years at 12% should be well above the simple sum
        assert fv > 5000 * 120
        assert fv == pytest.approx(1160000, rel=0.05)


class TestLumpsumFutureValue:
    def test_zero_years_returns_present_value(self):
        assert calculate_lumpsum_future_value(10000, 0, 10) == 10000

    def test_compounds_correctly(self):
        fv = calculate_lumpsum_future_value(100000, 5, 10)
        assert fv == pytest.approx(100000 * (1.10 ** 5), rel=1e-6)


class TestRequiredSip:
    def test_raises_on_zero_months(self):
        with pytest.raises(ValueError):
            calculate_required_sip(100000, 0, 12)

    def test_zero_return_divides_evenly(self):
        assert calculate_required_sip(12000, 12, 0) == 1000

    def test_required_sip_actually_reaches_target(self):
        target, months, rate = 1000000, 60, 12
        sip = calculate_required_sip(target, months, rate)
        achieved = calculate_future_value_of_contribution(sip, months, rate)
        assert achieved == pytest.approx(target, rel=1e-6)


class TestInflationAdjustedTarget:
    def test_zero_years_returns_present_value(self):
        assert inflation_adjusted_target(100000, 0, 6) == 100000

    def test_compounds_inflation_correctly(self):
        adjusted = inflation_adjusted_target(100000, 10, 6)
        assert adjusted == pytest.approx(100000 * (1.06 ** 10), rel=1e-6)

class TestGrowingAnnuityPv:
    def test_zero_periods_returns_zero(self):
        assert calculate_growing_annuity_pv(100000, 0, 7, 6) == 0

    def test_equal_rate_and_growth_uses_limiting_case(self):
        pv = calculate_growing_annuity_pv(100000, 10, 6, 6)
        assert pv == pytest.approx(100000 * 10 / 1.06, rel=1e-6)

    def test_positive_spread_produces_finite_positive_pv(self):
        pv = calculate_growing_annuity_pv(1000000, 25, 7, 6)
        assert pv > 0
        # sanity: PV should be less than the undiscounted sum of all
        # (growing) payments, since money later is worth less today
        undiscounted_sum = sum(1000000 * (1.06 ** i) for i in range(25))
        assert pv < undiscounted_sum

class TestGrowingAnnuityPv:
    def test_zero_periods_returns_zero(self):
        assert calculate_growing_annuity_pv(100000, 0, 7, 6) == 0

    def test_equal_rate_and_growth_uses_limiting_case(self):
        pv = calculate_growing_annuity_pv(100000, 10, 6, 6)
        assert pv == pytest.approx(100000 * 10 / 1.06, rel=1e-6)

    def test_positive_spread_produces_finite_positive_pv(self):
        pv = calculate_growing_annuity_pv(1000000, 25, 7, 6)
        assert pv > 0
        undiscounted_sum = sum(1000000 * (1.06 ** i) for i in range(25))
        assert pv < undiscounted_sum