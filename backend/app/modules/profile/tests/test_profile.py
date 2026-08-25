import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.middleware.auth import get_current_user, get_access_token
from app.modules.auth.schemas import UserOut

client = TestClient(app)

FAKE_USER = UserOut(id="user-123", email="test@example.com")

FAKE_ROW = {
    "id": "row-1",
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


@pytest.fixture(autouse=True)
def override_auth():
    """Runs around every test in this file: swaps the real auth dependency
    for a fake logged-in user, and cleans up afterward so other test files
    aren't affected."""
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[get_access_token] = lambda: "fake-token"
    yield
    app.dependency_overrides.clear()


def auth_headers():
    return {"Authorization": "Bearer good-token"}


class TestCreateProfile:
    def test_creates_profile(self):
        with patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=None), \
             patch("app.modules.profile.repository.ProfileRepository.create", return_value=FAKE_ROW):
            res = client.post(
                "/api/v1/profile",
                json={"monthly_income": 80000, "monthly_expenses": 40000, "dependents": 1, "employment_type": "salaried"},
                headers=auth_headers(),
            )
        assert res.status_code == 201
        assert res.json()["monthly_surplus"] == 40000

    def test_rejects_duplicate_profile(self):
        with patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=FAKE_ROW):
            res = client.post("/api/v1/profile", json={}, headers=auth_headers())
        assert res.status_code == 409

    def test_rejects_negative_income(self):
        res = client.post(
            "/api/v1/profile",
            json={"monthly_income": -100},
            headers=auth_headers(),
        )
        assert res.status_code == 422


class TestGetProfile:
    def test_returns_404_when_missing(self):
        with patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=None):
            res = client.get("/api/v1/profile", headers=auth_headers())
        assert res.status_code == 404

    def test_returns_profile_with_computed_surplus(self):
        with patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=FAKE_ROW):
            res = client.get("/api/v1/profile", headers=auth_headers())
        assert res.status_code == 200
        assert res.json()["monthly_surplus"] == 40000


class TestUpdateProfile:
    def test_returns_404_when_missing(self):
        with patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=None):
            res = client.put("/api/v1/profile", json={"monthly_income": 90000}, headers=auth_headers())
        assert res.status_code == 404

    def test_updates_only_provided_fields(self):
        updated_row = {**FAKE_ROW, "monthly_income": 90000}
        with patch("app.modules.profile.repository.ProfileRepository.get_by_user_id", return_value=FAKE_ROW), \
             patch("app.modules.profile.repository.ProfileRepository.update", return_value=updated_row) as mock_update:
            res = client.put("/api/v1/profile", json={"monthly_income": 90000}, headers=auth_headers())
        assert res.status_code == 200
        assert res.json()["monthly_income"] == 90000
        mock_update.assert_called_once()
        assert mock_update.call_args[0][2] == {"monthly_income": 90000}