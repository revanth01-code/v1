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
    "monthly_income": 80000,
    "monthly_expenses": 40000,
    "existing_savings": 100000,
    "existing_investments": 50000,
    "dependents": 1,
    "employment_type": "salaried",
    "created_at": "2026-08-09T00:00:00Z",
    "updated_at": "2026-08-09T00:00:00Z",
}

FAKE_EF_ROW = {
    "id": "ef-1",
    "user_id": "user-123",
    "months_of_coverage": 3,
    "current_amount": 30000,
    "monthly_contribution": 5000,
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
    def test_requires_profile_to_exist_first(self):
        with patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id", return_value=None), \
             patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=None):
            res = client.post("/api/v1/emergency-fund", json={})
        assert res.status_code == 422

    def test_creates_with_default_3_month_coverage(self):
        with patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id", return_value=None), \
             patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=FAKE_PROFILE), \
             patch("app.modules.emergency_fund.repository.EmergencyFundRepository.create", return_value=FAKE_EF_ROW) as mock_create:
            res = client.post("/api/v1/emergency-fund", json={"current_amount": 30000, "monthly_contribution": 5000})

        assert res.status_code == 201
        body = res.json()
        assert body["monthly_expenses"] == 40000
        assert body["target_amount"] == 120000  # 40000 * 3
        # confirm the default of 3 was actually sent to the DB layer
        assert mock_create.call_args[0][2]["months_of_coverage"] == 3

    def test_computes_time_to_target_correctly(self):
        with patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id", return_value=None), \
             patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=FAKE_PROFILE), \
             patch("app.modules.emergency_fund.repository.EmergencyFundRepository.create", return_value=FAKE_EF_ROW):
            res = client.post("/api/v1/emergency-fund", json={"current_amount": 30000, "monthly_contribution": 5000})

        body = res.json()
        # target 120000, current 30000, remaining 90000, /5000 per month = 18 months
        assert body["time_to_target_months"] == 18.0

    def test_rejects_duplicate(self):
        with patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id", return_value=FAKE_EF_ROW):
            res = client.post("/api/v1/emergency-fund", json={})
        assert res.status_code == 409


class TestGet:
    def test_returns_404_when_missing(self):
        with patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id", return_value=None):
            res = client.get("/api/v1/emergency-fund")
        assert res.status_code == 404

    def test_status_complete_when_target_reached(self):
        fully_funded_row = {**FAKE_EF_ROW, "current_amount": 200000}
        with patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id", return_value=fully_funded_row), \
             patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=FAKE_PROFILE):
            res = client.get("/api/v1/emergency-fund")
        assert res.status_code == 200
        assert res.json()["status"] == "complete"
        assert res.json()["time_to_target_months"] == 0.0  # already there — zero months remainingss

    def test_status_building_when_below_target(self):
        with patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id", return_value=FAKE_EF_ROW), \
             patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=FAKE_PROFILE):
            res = client.get("/api/v1/emergency-fund")
        assert res.status_code == 200
        assert res.json()["status"] == "building"

    def test_null_time_to_target_when_contribution_is_zero(self):
        zero_contribution_row = {**FAKE_EF_ROW, "monthly_contribution": 0}
        with patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id", return_value=zero_contribution_row), \
             patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=FAKE_PROFILE):
            res = client.get("/api/v1/emergency-fund")
        assert res.json()["time_to_target_months"] is None


class TestUpdate:
    def test_reflects_new_profile_expenses_automatically(self):
        """Core point of the auto-pull design: if the user's income/expenses
        change later in their profile, the emergency fund target should
        reflect that immediately without needing its own update."""
        updated_profile = {**FAKE_PROFILE, "monthly_expenses": 50000}
        with patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id", return_value=FAKE_EF_ROW), \
             patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=updated_profile):
            res = client.get("/api/v1/emergency-fund")
        assert res.json()["monthly_expenses"] == 50000
        assert res.json()["target_amount"] == 150000  # 50000 * 3