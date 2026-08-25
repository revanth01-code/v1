import pytest
from datetime import date, timedelta
from app.core.exceptions import AppError
from app.modules.feasibility_engine.schemas import FeasibilityInput
from app.modules.feasibility_engine.service import FeasibilityEngine


def make_input(**overrides):
    defaults = dict(
        target_amount=1000000,
        target_date=date.today() + timedelta(days=365 * 5),
        monthly_contribution=15000,
        lumpsum_amount=0,
        expected_return_pct=12,
        inflation_pct=6,
    )
    defaults.update(overrides)
    return FeasibilityInput(**defaults)


class TestFeasible:
    def test_well_funded_goal_is_feasible(self):
        result = FeasibilityEngine.check(make_input(monthly_contribution=20000))
        assert result.status == "feasible"
        assert result.shortfall is None

    def test_lumpsum_only_can_be_feasible(self):
        result = FeasibilityEngine.check(
            make_input(monthly_contribution=0, lumpsum_amount=800000)
        )
        assert result.status == "feasible"


class TestBorderline:
    def test_close_shortfall_is_borderline(self):
        baseline = make_input(monthly_contribution=1)
        result_for_months = FeasibilityEngine.check(baseline)

        from app.lib.finance_math import calculate_required_sip
        required_sip = calculate_required_sip(
            result_for_months.inflation_adjusted_target,
            result_for_months.months,
            12,
        )

        borderline_contribution = required_sip * 0.90
        result = FeasibilityEngine.check(make_input(monthly_contribution=borderline_contribution))

        assert result.status == "borderline"
        assert result.suggested_monthly_sip is not None
        assert result.suggested_monthly_sip > borderline_contribution


class TestInfeasible:
    def test_tiny_contribution_is_infeasible(self):
        result = FeasibilityEngine.check(make_input(monthly_contribution=500))
        assert result.status == "infeasible"
        assert result.shortfall > 0
        assert result.suggested_monthly_sip is not None
        assert result.suggested_monthly_sip > 500

    def test_infeasible_suggests_extended_duration(self):
        result = FeasibilityEngine.check(make_input(monthly_contribution=1000))
        assert result.status == "infeasible"
        assert result.suggested_extended_months is not None
        assert result.suggested_extended_months > result.months

    def test_zero_contribution_infeasible_with_no_extended_months_found(self):
        result = FeasibilityEngine.check(
            make_input(monthly_contribution=0, lumpsum_amount=0)
        )
        assert result.status == "infeasible"
        assert result.suggested_extended_months is None


class TestEdgeCases:
    def test_past_target_date_raises(self):
        with pytest.raises(AppError):
            FeasibilityEngine.check(
                make_input(target_date=date.today() - timedelta(days=1))
            )

    def test_suggested_sip_actually_closes_the_gap(self):
        result = FeasibilityEngine.check(make_input(monthly_contribution=500))
        assert result.suggested_monthly_sip is not None

        retried = FeasibilityEngine.check(
            make_input(monthly_contribution=result.suggested_monthly_sip)
        )
        assert retried.status == "feasible"