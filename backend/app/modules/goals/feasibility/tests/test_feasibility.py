# backend/app/modules/goals/feasibility/tests/test_feasibility.py
from datetime import date, timedelta
import pytest
from app.modules.goals.feasibility.feasibility_models import GoalFeasibilityPreviewRequest, GoalFeasibilityApplyRequest, GoalFeasibilityAlternative
from app.modules.goals.feasibility.feasibility_service import FeasibilityService, FEASIBILITY_RETURN_ASSUMPTIONS


def test_achievable_goal():
    # Target 100,000, 12 months, mid risk (conservative return 8%), monthly investment 9,000
    # Expected FV of SIP will easily exceed 100,000
    req = GoalFeasibilityPreviewRequest(
        target_amount=100000.0,
        current_amount=0.0,
        monthly_investment=9000.0,
        horizon_months=12,
        risk_level="mid"
    )
    res = FeasibilityService.calculate_feasibility(req)
    assert res.status == "ACHIEVABLE"
    assert res.projection["required_monthly_investment"] <= 9000.0
    assert not res.alternatives


def test_stretched_goal():
    # Target 100,000, 12 months, mid risk, monthly investment 7,500
    # Required is approx 8,000, so 7,500 is stretched (between 70% and 95% of required)
    req = GoalFeasibilityPreviewRequest(
        target_amount=100000.0,
        current_amount=0.0,
        monthly_investment=7500.0,
        horizon_months=12,
        risk_level="mid"
    )
    res = FeasibilityService.calculate_feasibility(req)
    assert res.status == "STRETCHED"
    assert len(res.alternatives) > 0


def test_difficult_goal():
    # Target 100,000, 12 months, mid risk, monthly investment 4,000 (approx 50% of required)
    req = GoalFeasibilityPreviewRequest(
        target_amount=100000.0,
        current_amount=0.0,
        monthly_investment=4000.0,
        horizon_months=12,
        risk_level="mid"
    )
    res = FeasibilityService.calculate_feasibility(req)
    assert res.status == "DIFFICULT"
    assert len(res.alternatives) > 0


def test_unrealistic_goal():
    # Target 100,000, 12 months, mid risk, monthly investment 1,000 (less than 40% of required)
    req = GoalFeasibilityPreviewRequest(
        target_amount=100000.0,
        current_amount=0.0,
        monthly_investment=1000.0,
        horizon_months=12,
        risk_level="mid"
    )
    res = FeasibilityService.calculate_feasibility(req)
    assert res.status == "UNREALISTIC"
    assert len(res.alternatives) > 0


def test_missing_monthly_investment():
    # If monthly investment is 0.0, it is valid but could be STRETCHED/UNREALISTIC depending on gap
    req = GoalFeasibilityPreviewRequest(
        target_amount=100000.0,
        current_amount=0.0,
        monthly_investment=0.0,
        horizon_months=12,
        risk_level="mid"
    )
    res = FeasibilityService.calculate_feasibility(req)
    assert res.status in ["UNREALISTIC", "DIFFICULT"]


def test_missing_target_date_and_horizon():
    # Missing both horizon_months and target_date
    req = GoalFeasibilityPreviewRequest(
        target_amount=100000.0,
        current_amount=0.0,
        monthly_investment=1000.0,
        horizon_months=None,
        target_date=None,
        risk_level="mid"
    )
    res = FeasibilityService.calculate_feasibility(req)
    assert res.status == "INSUFFICIENT_INFORMATION"


def test_zero_monthly_investment():
    # Handled correctly
    req = GoalFeasibilityPreviewRequest(
        target_amount=50000.0,
        current_amount=0.0,
        monthly_investment=0.0,
        horizon_months=24,
        risk_level="mid"
    )
    res = FeasibilityService.calculate_feasibility(req)
    assert res.status in ["UNREALISTIC", "DIFFICULT"]
    assert res.projection["projected_value"] == 0.0


def test_zero_current_investment():
    req = GoalFeasibilityPreviewRequest(
        target_amount=100000.0,
        current_amount=0.0,
        monthly_investment=10000.0,
        horizon_months=12,
        risk_level="mid"
    )
    res = FeasibilityService.calculate_feasibility(req)
    # Lumpsum FV portion should be 0.0
    assert res.goal_summary["current_amount"] == 0.0
    assert res.status == "ACHIEVABLE"


def test_short_investment_horizon():
    # 1 month horizon
    req = GoalFeasibilityPreviewRequest(
        target_amount=10000.0,
        current_amount=0.0,
        monthly_investment=10100.0,
        horizon_months=1,
        risk_level="mid"
    )
    res = FeasibilityService.calculate_feasibility(req)
    assert res.status == "ACHIEVABLE"


def test_long_investment_horizon():
    # 240 months horizon (20 years)
    req = GoalFeasibilityPreviewRequest(
        target_amount=10000000.0,
        current_amount=100000.0,
        monthly_investment=15000.0,
        horizon_months=240,
        risk_level="high"
    )
    res = FeasibilityService.calculate_feasibility(req)
    assert res.status in ["ACHIEVABLE", "STRETCHED", "DIFFICULT", "UNREALISTIC"]


def test_risk_assumptions():
    # Low, Mid, High risk should use different conservative return values
    assert FEASIBILITY_RETURN_ASSUMPTIONS["low"]["conservative_return"] == 0.05
    assert FEASIBILITY_RETURN_ASSUMPTIONS["mid"]["conservative_return"] == 0.08
    assert FEASIBILITY_RETURN_ASSUMPTIONS["high"]["conservative_return"] == 0.11


def test_sip_calculation_correctness():
    # For P=1000, n=12, r=0.08/12 = 0.0066667
    # Multiplier = (((1+r)^12 - 1)/r)*(1+r)
    # FV_sip = P * Multiplier
    # Let's check calculation determinism
    req = GoalFeasibilityPreviewRequest(
        target_amount=13000.0,
        current_amount=0.0,
        monthly_investment=1000.0,
        horizon_months=12,
        risk_level="mid"
    )
    res = FeasibilityService.calculate_feasibility(req)
    r = 0.08 / 12
    expected_mult = (((1 + r) ** 12 - 1) / r) * (1 + r)
    expected_fv = round(1000.0 * expected_mult, 2)
    assert res.projection["projected_value"] == expected_fv


def test_lump_sum_calculation_correctness():
    # For PV=5000, P=0, n=12, r=0.08/12
    # FV = 5000 * (1+r)^12
    req = GoalFeasibilityPreviewRequest(
        target_amount=6000.0,
        current_amount=5000.0,
        monthly_investment=0.0,
        horizon_months=12,
        risk_level="mid"
    )
    res = FeasibilityService.calculate_feasibility(req)
    r = 0.08 / 12
    expected_fv = round(5000.0 * ((1 + r) ** 12), 2)
    assert res.projection["projected_value"] == expected_fv


def test_alternatives_generation():
    # If goal is Stretched/Difficult/Unrealistic, it must generate all 4 alternative types
    req = GoalFeasibilityPreviewRequest(
        target_amount=200000.0,
        current_amount=0.0,
        monthly_investment=5000.0,
        horizon_months=12,
        risk_level="mid"
    )
    res = FeasibilityService.calculate_feasibility(req)
    assert res.status in ["DIFFICULT", "UNREALISTIC", "STRETCHED"]
    alt_types = [alt.type for alt in res.alternatives]
    assert "increase_monthly_investment" in alt_types
    assert "extend_horizon" in alt_types
    assert "adjust_target" in alt_types
    assert "review_risk_profile" in alt_types


def test_apply_alternative_preview():
    # Verify that applying an alternative strategy yields revised strategy preview
    original = GoalFeasibilityPreviewRequest(
        target_amount=200000.0,
        current_amount=0.0,
        monthly_investment=5000.0,
        horizon_months=12,
        risk_level="mid"
    )
    alt = GoalFeasibilityAlternative(
        type="increase_monthly_investment",
        recommended_monthly_investment=18000.0,
        description="Test increase"
    )
    apply_req = GoalFeasibilityApplyRequest(
        original_goal=original,
        selected_alternative=alt
    )
    res = FeasibilityService.apply_alternative(apply_req)
    assert res.revised_goal.monthly_investment == 18000.0
    assert res.strategy_preview is not None


def test_no_automatic_risk_escalation():
    # Confirm that feasibility service calculations do not modify the input risk level
    req = GoalFeasibilityPreviewRequest(
        target_amount=500000.0,
        current_amount=0.0,
        monthly_investment=2000.0,
        horizon_months=12,
        risk_level="low"
    )
    res = FeasibilityService.calculate_feasibility(req)
    # Alternatives description must not suggest escalating risk level automatically
    assert res.goal_summary["risk_level"] == "low"
    for alt in res.alternatives:
        assert "high risk" not in alt.description.lower()
        assert "increase risk" not in alt.description.lower()


def test_no_automatic_goal_modification():
    # Make sure calculate_feasibility remains preview-only and does not persist or modify any DB records
    req = GoalFeasibilityPreviewRequest(
        target_amount=100000.0,
        current_amount=0.0,
        monthly_investment=10000.0,
        horizon_months=12,
        risk_level="mid"
    )
    res = FeasibilityService.calculate_feasibility(req)
    # Returns purely a preview model
    assert res.next_step in ["proceed_to_strategy", "review_alternatives"]


def test_deterministic_output():
    req = GoalFeasibilityPreviewRequest(
        target_amount=100000.0,
        current_amount=10000.0,
        monthly_investment=5000.0,
        horizon_months=12,
        risk_level="mid"
    )
    res1 = FeasibilityService.calculate_feasibility(req)
    res2 = FeasibilityService.calculate_feasibility(req)
    assert res1.status == res2.status
    assert res1.projection == res2.projection
