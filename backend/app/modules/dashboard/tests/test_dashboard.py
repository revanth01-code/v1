import pytest
from datetime import date
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.core.exceptions import AppError
from app.middleware.auth import get_current_user, get_access_token
from app.modules.auth.schemas import UserOut
from app.modules.goals.schemas import GoalOut
from app.modules.retirement.schemas import RetirementOut
from app.modules.emergency_fund.schemas import EmergencyFundOut

client = TestClient(app)
FAKE_USER = UserOut(id="user-123", email="test@example.com")


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[get_access_token] = lambda: "fake-token"
    yield
    app.dependency_overrides.clear()


def make_goal(**overrides):
    defaults = dict(
        id="goal-1",
        user_id="user-123",
        name="Car",
        target_amount=800000,
        target_date=date(2029, 1, 1),
        term_type="long_term",
        contribution_mode="sip",
        monthly_contribution=20000,
        lumpsum_amount=0,
        risk_level="mid",
        fund_category_mix={"largecap": 40, "flexicap": 40, "debt": 20},
        expected_return_pct=10.0,
        inflation_adjusted_target=900000,
        feasibility_status="feasible",
        feasibility_details=None,
        status="active",
        created_at="2026-08-09T00:00:00Z",
        updated_at="2026-08-09T00:00:00Z",
        recommended_funds={},
    )
    defaults.update(overrides)
    return GoalOut(**defaults)


class TestDashboard:
    def test_requires_auth(self):
        app.dependency_overrides.clear()
        res = client.get("/api/v1/dashboard")
        assert res.status_code == 401

    def test_full_dashboard_when_everything_set_up(self):
        fake_retirement = RetirementOut(
            id="ret-1", user_id="user-123", current_age=30, retirement_age=60,
            life_expectancy=85, existing_retirement_corpus=500000,
            planned_monthly_contribution=25000, inflation_pct=6,
            pre_retirement_return_pct=11, post_retirement_return_pct=7,
            current_monthly_expense=60000, years_to_retirement=30,
            years_in_retirement=25, required_corpus=30000000,
            feasibility_status="borderline", feasibility_details={},
            created_at="2026-08-09T00:00:00Z", updated_at="2026-08-09T00:00:00Z",
        )
        fake_ef = EmergencyFundOut(
            id="ef-1", user_id="user-123", months_of_coverage=3,
            current_amount=30000, monthly_contribution=5000,
            monthly_expenses=40000, target_amount=120000,
            time_to_target_months=18.0, status="building",
            created_at="2026-08-09T00:00:00Z", updated_at="2026-08-09T00:00:00Z",
        )

        with patch("app.modules.dashboard.service.ProfileService.get_profile", return_value=object()), \
             patch("app.modules.dashboard.service.GoalService.list_goals",
                   return_value=[make_goal(), make_goal(id="goal-2", feasibility_status="borderline")]), \
             patch("app.modules.dashboard.service.RetirementService.get", return_value=fake_retirement), \
             patch("app.modules.dashboard.service.EmergencyFundService.get", return_value=fake_ef):
            res = client.get("/api/v1/dashboard")

        assert res.status_code == 200
        body = res.json()
        assert body["profile_complete"] is True
        assert body["goals"]["total"] == 2
        assert body["goals"]["feasible"] == 1
        assert body["goals"]["borderline"] == 1
        assert body["retirement"]["feasibility_status"] == "borderline"
        assert body["emergency_fund"]["status"] == "building"

    def test_null_sections_when_nothing_set_up_yet(self):
        with patch("app.modules.dashboard.service.ProfileService.get_profile",
                   side_effect=AppError("not found", 404)), \
             patch("app.modules.dashboard.service.GoalService.list_goals", return_value=[]), \
             patch("app.modules.dashboard.service.RetirementService.get",
                   side_effect=AppError("not found", 404)), \
             patch("app.modules.dashboard.service.EmergencyFundService.get",
                   side_effect=AppError("not found", 404)):
            res = client.get("/api/v1/dashboard")

        assert res.status_code == 200
        body = res.json()
        assert body["profile_complete"] is False
        assert body["goals"]["total"] == 0
        assert body["retirement"] is None
        assert body["emergency_fund"] is None