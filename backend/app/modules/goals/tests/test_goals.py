import pytest
from datetime import date, timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.middleware.auth import get_current_user, get_access_token
from app.modules.auth.schemas import UserOut
from app.modules.funds.schemas import FundOut

client = TestClient(app)
FAKE_USER = UserOut(id="user-123", email="test@example.com")


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[get_access_token] = lambda: "fake-token"
    yield
    app.dependency_overrides.clear()


def far_future_date(years=5):
    return (date.today() + timedelta(days=365 * years)).isoformat()


def near_future_date(months=12):
    return (date.today() + timedelta(days=30 * months)).isoformat()


def base_payload(**overrides):
    payload = {
        "name": "House Downpayment",
        "target_amount": 1000000,
        "target_date": far_future_date(),
        "contribution_mode": "sip",
        "monthly_contribution": 20000,
        "lumpsum_amount": 0,
        "risk_level": "mid",
    }
    payload.update(overrides)
    return payload


FAKE_ROW = {
    "id": "goal-1",
    "user_id": "user-123",
    "name": "House Downpayment",
    "target_amount": 1000000,
    "target_date": far_future_date(),
    "term_type": "long_term",
    "contribution_mode": "sip",
    "monthly_contribution": 20000,
    "lumpsum_amount": 0,
    "risk_level": "mid",
    "fund_category_mix": {"largecap": 40, "flexicap": 40, "debt": 20},
    "expected_return_pct": 10.0,
    "inflation_adjusted_target": 1300000,
    "feasibility_status": "feasible",
    "feasibility_details": {"status": "feasible"},
    "status": "active",
    "created_at": "2026-08-09T00:00:00Z",
    "updated_at": "2026-08-09T00:00:00Z",
}

FAKE_FUND = FundOut(
    scheme_code="100001",
    scheme_name="ABC Large Cap Fund - Direct Plan-Growth",
    category="largecap",
    latest_nav=150.25,
    nav_date="09-Aug-2026",
)


class TestRecommendedFunds:
    def test_create_includes_recommended_funds_per_category(self):
        with patch("app.modules.goals.repository.GoalRepository.create", return_value=FAKE_ROW), \
             patch("app.modules.funds.service.FundService.get_funds_by_category", return_value=[FAKE_FUND]):
            res = client.post("/api/v1/goals", json=base_payload(monthly_contribution=25000))
        assert res.status_code == 201
        recommended = res.json()["recommended_funds"]
        assert "largecap" in recommended
        assert recommended["largecap"][0]["scheme_code"] == "100001"

    def test_degrades_gracefully_when_fund_service_fails(self):
        with patch("app.modules.goals.repository.GoalRepository.create", return_value=FAKE_ROW), \
             patch("app.modules.funds.service.FundService.get_funds_by_category", side_effect=Exception("funds down")):
            res = client.post("/api/v1/goals", json=base_payload(monthly_contribution=25000))
        assert res.status_code == 201  # goal creation still succeeds
        recommended = res.json()["recommended_funds"]
        assert all(v == [] for v in recommended.values())


class TestCheckEndpoint:
    def test_check_does_not_require_auth(self):
        app.dependency_overrides.clear()  # prove /check works with no auth at all
        res = client.post("/api/v1/goals/check", json=base_payload())
        assert res.status_code == 200

    def test_feasible_goal_returns_feasible(self):
        res = client.post("/api/v1/goals/check", json=base_payload(monthly_contribution=25000))
        assert res.status_code == 200
        assert res.json()["feasibility"]["status"] in ("feasible", "borderline")

    def test_short_term_high_risk_triggers_guardrail(self):
        res = client.post(
            "/api/v1/goals/check",
            json=base_payload(target_date=near_future_date(12), risk_level="high"),
        )
        assert res.status_code == 200
        assert res.json()["guardrail"]["allowed"] is False

    def test_rejects_sip_mode_with_zero_contribution(self):
        res = client.post(
            "/api/v1/goals/check",
            json=base_payload(contribution_mode="sip", monthly_contribution=0),
        )
        assert res.status_code == 422


class TestCreateGoal:
    def test_requires_auth(self):
        app.dependency_overrides.clear()
        res = client.post("/api/v1/goals", json=base_payload())
        assert res.status_code == 401

    def test_creates_feasible_goal(self):
        with patch("app.modules.goals.repository.GoalRepository.create", return_value=FAKE_ROW):
            res = client.post(
                "/api/v1/goals",
                json=base_payload(monthly_contribution=25000),
            )
        assert res.status_code == 201
        assert res.json()["feasibility_status"] in ("feasible", "borderline")

    def test_blocks_infeasible_goal(self):
        res = client.post("/api/v1/goals", json=base_payload(monthly_contribution=100))
        assert res.status_code == 422
        body = res.json()
        assert "feasibility" in body
        assert body["feasibility"]["status"] == "infeasible"
        assert body["feasibility"]["suggested_monthly_sip"] is not None

    def test_blocks_short_term_high_risk_before_even_checking_feasibility(self):
        res = client.post(
            "/api/v1/goals",
            json=base_payload(
                target_date=near_future_date(12),
                risk_level="high",
                monthly_contribution=100000,  # even a huge, clearly-feasible SIP
            ),
        )
        assert res.status_code == 422
        assert "feasibility" not in res.json()  # guardrail should block before feasibility even matters


class TestListAndGetGoals:
    def test_list_goals(self):
        with patch("app.modules.goals.repository.GoalRepository.list_by_user", return_value=[FAKE_ROW]):
            res = client.get("/api/v1/goals")
        assert res.status_code == 200
        assert len(res.json()) == 1

    def test_get_goal_not_found(self):
        with patch("app.modules.goals.repository.GoalRepository.get_by_id", return_value=None):
            res = client.get("/api/v1/goals/nonexistent-id")
        assert res.status_code == 404

    def test_get_goal_found(self):
        with patch("app.modules.goals.repository.GoalRepository.get_by_id", return_value=FAKE_ROW):
            res = client.get("/api/v1/goals/goal-1")
        assert res.status_code == 200
        assert res.json()["id"] == "goal-1"