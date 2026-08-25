import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.middleware.auth import get_current_user, get_access_token
from app.modules.auth.schemas import UserOut

client = TestClient(app)
FAKE_USER = UserOut(id="user-123", email="test@example.com")

FAKE_PROFILE = {
    "id": "profile-1",
    "user_id": "user-123",
    "monthly_income": 150000,
    "monthly_expenses": 60000,
    "existing_savings": 500000,
    "existing_investments": 300000,
    "dependents": 2,
    "employment_type": "salaried",
    "created_at": "2026-08-09T00:00:00Z",
    "updated_at": "2026-08-09T00:00:00Z",
}

FAKE_RETIREMENT_ROW = {
    "id": "ret-1",
    "user_id": "user-123",
    "current_age": 30,
    "retirement_age": 60,
    "life_expectancy": 85,
    "existing_retirement_corpus": 500000,
    "planned_monthly_contribution": 25000,
    "inflation_pct": 6,
    "pre_retirement_return_pct": 11,
    "post_retirement_return_pct": 7,
    "created_at": "2026-08-09T00:00:00Z",
    "updated_at": "2026-08-09T00:00:00Z",
}


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[get_access_token] = lambda: "fake-token"
    yield
    app.dependency_overrides.clear()


class TestCreate:
    def test_requires_profile_first(self):
        with patch("app.modules.retirement.repository.RetirementRepository.get_by_user_id", return_value=None), \
             patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=None):
            res = client.post(
                "/api/v1/retirement",
                json={"current_age": 30, "retirement_age": 60},
            )
        assert res.status_code == 422

    def test_creates_plan_with_defaults(self):
        with patch("app.modules.retirement.repository.RetirementRepository.get_by_user_id", return_value=None), \
             patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=FAKE_PROFILE), \
             patch("app.modules.retirement.repository.RetirementRepository.create", return_value=FAKE_RETIREMENT_ROW):
            res = client.post(
                "/api/v1/retirement",
                json={"current_age": 30, "retirement_age": 60, "planned_monthly_contribution": 25000, "existing_retirement_corpus": 500000},
            )
        assert res.status_code == 201
        body = res.json()
        assert body["years_to_retirement"] == 30
        assert body["years_in_retirement"] == 25
        assert body["required_corpus"] > 0
        assert body["feasibility_status"] in ("feasible", "borderline", "infeasible")

    def test_does_not_block_on_infeasible(self):
        """Key product decision: unlike goals, retirement plans should save
        even when infeasible — the status is informational, not a gate."""
        underfunded_row = {**FAKE_RETIREMENT_ROW, "planned_monthly_contribution": 500}
        with patch("app.modules.retirement.repository.RetirementRepository.get_by_user_id", return_value=None), \
             patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=FAKE_PROFILE), \
             patch("app.modules.retirement.repository.RetirementRepository.create", return_value=underfunded_row):
            res = client.post(
                "/api/v1/retirement",
                json={"current_age": 30, "retirement_age": 60, "planned_monthly_contribution": 500},
            )
        assert res.status_code == 201  # created despite being infeasible
        assert res.json()["feasibility_status"] == "infeasible"

    def test_rejects_retirement_age_before_current_age(self):
        res = client.post(
            "/api/v1/retirement",
            json={"current_age": 60, "retirement_age": 40},
        )
        assert res.status_code == 422

    def test_rejects_life_expectancy_before_retirement_age(self):
        res = client.post(
            "/api/v1/retirement",
            json={"current_age": 30, "retirement_age": 60, "life_expectancy": 55},
        )
        assert res.status_code == 422

    def test_rejects_duplicate(self):
        with patch("app.modules.retirement.repository.RetirementRepository.get_by_user_id", return_value=FAKE_RETIREMENT_ROW):
            res = client.post(
                "/api/v1/retirement",
                json={"current_age": 30, "retirement_age": 60},
            )
        assert res.status_code == 409


class TestGet:
    def test_returns_404_when_missing(self):
        with patch("app.modules.retirement.repository.RetirementRepository.get_by_user_id", return_value=None):
            res = client.get("/api/v1/retirement")
        assert res.status_code == 404

    def test_returns_plan_with_computed_fields(self):
        with patch("app.modules.retirement.repository.RetirementRepository.get_by_user_id", return_value=FAKE_RETIREMENT_ROW), \
             patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=FAKE_PROFILE):
            res = client.get("/api/v1/retirement")
        assert res.status_code == 200
        body = res.json()
        assert body["current_monthly_expense"] == 60000
        assert body["required_corpus"] > 0

    def test_higher_planned_contribution_improves_feasibility(self):
        """Sanity check that the math direction makes sense: more monthly
        contribution should never make feasibility worse."""
        low_contribution_row = {**FAKE_RETIREMENT_ROW, "planned_monthly_contribution": 1000}
        high_contribution_row = {**FAKE_RETIREMENT_ROW, "planned_monthly_contribution": 100000}

        with patch("app.modules.retirement.repository.RetirementRepository.get_by_user_id", return_value=low_contribution_row), \
             patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=FAKE_PROFILE):
            low_res = client.get("/api/v1/retirement")

        with patch("app.modules.retirement.repository.RetirementRepository.get_by_user_id", return_value=high_contribution_row), \
             patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=FAKE_PROFILE):
            high_res = client.get("/api/v1/retirement")

        status_rank = {"infeasible": 0, "borderline": 1, "feasible": 2}
        assert status_rank[high_res.json()["feasibility_status"]] >= status_rank[low_res.json()["feasibility_status"]]


class TestUpdate:
    def test_returns_404_when_missing(self):
        with patch("app.modules.retirement.repository.RetirementRepository.get_by_user_id", return_value=None):
            res = client.put("/api/v1/retirement", json={"planned_monthly_contribution": 30000})
        assert res.status_code == 404

    def test_rejects_invalid_age_ordering_on_merge(self):
        with patch("app.modules.retirement.repository.RetirementRepository.get_by_user_id", return_value=FAKE_RETIREMENT_ROW), \
             patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=FAKE_PROFILE):
            res = client.put("/api/v1/retirement", json={"retirement_age": 25})
        assert res.status_code == 422