"""
Regression tests for the PostgREST APIError global exception handler.

These tests verify:
  1. PGRST301 (invalid/expired JWT on the DB connection) -> HTTP 401
  2. 42501 (RLS violation) -> HTTP 403
  3. 23514 / 23502 (constraint violations) -> HTTP 400
  4. Unknown DB error -> HTTP 500 (not hidden as 400/403)
  5. Valid goal creation still succeeds (regression guard)
  6. Sensitive database details never appear in API responses
"""
import pytest
from datetime import date, timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.main import app
from app.middleware.auth import get_current_user, get_access_token
from app.modules.auth.schemas import UserOut

client = TestClient(app)
FAKE_USER = UserOut(id="user-db-error-test", email="dberror@example.com")


def _make_api_error(code: str, message: str, details: str = "") -> APIError:
    """Build a postgrest APIError that matches what the real client raises."""
    err = APIError.__new__(APIError)
    err.code    = code
    err.message = message
    err.details = details
    err.hint    = None
    err.args    = (str({"code": code, "message": message, "details": details, "hint": None}),)
    return err


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[get_access_token] = lambda: "fake-token"
    yield
    app.dependency_overrides.clear()


def _feasible_payload(**overrides) -> dict:
    base = {
        "name": "Error Handling Test Goal",
        "target_amount": 500000,
        "target_date": (date.today() + timedelta(days=365 * 5)).isoformat(),
        "contribution_mode": "sip",
        "monthly_contribution": 15000,
        "lumpsum_amount": 0,
        "risk_level": "mid",
    }
    base.update(overrides)
    return base


FAKE_ROW = {
    "id": "goal-err-1",
    "user_id": "user-db-error-test",
    "name": "Error Handling Test Goal",
    "target_amount": 500000,
    "target_date": (date.today() + timedelta(days=365 * 5)).isoformat(),
    "term_type": "long_term",
    "contribution_mode": "sip",
    "monthly_contribution": 15000,
    "lumpsum_amount": 0,
    "risk_level": "mid",
    "fund_category_mix": {"largecap": 40, "flexicap": 40, "debt": 20},
    "expected_return_pct": 10.0,
    "inflation_adjusted_target": 620000.0,
    "feasibility_status": "feasible",
    "feasibility_details": {"status": "feasible"},
    "status": "active",
    "created_at": "2026-08-30T00:00:00Z",
    "updated_at": "2026-08-30T00:00:00Z",
}


class TestPostgRESTAPIErrorHandler:
    """Verify the global APIError handler returns correct HTTP status codes."""

    def test_invalid_jwt_on_db_write_returns_401(self):
        """
        Reproduces the original production 500 bug:
        GoalRepository.create raises PGRST301 (JWT validation failure in PostgREST).
        Handler must now return 401, not 500.
        """
        jwt_error = _make_api_error(
            "PGRST301",
            "No suitable key or wrong key type",
            "None of the keys was able to decode the JWT",
        )
        with patch(
            "app.modules.goals.repository.GoalRepository.create",
            side_effect=jwt_error,
        ):
            res = client.post("/api/v1/goals", json=_feasible_payload())

        assert res.status_code == 401, f"Expected 401, got {res.status_code}: {res.text}"
        body = res.json()
        assert "error" in body

    def test_rls_violation_returns_403(self):
        """RLS policy blocks the insert -> 403 Forbidden."""
        rls_error = _make_api_error(
            "42501",
            'new row violates row-level security policy for table "goals"',
        )
        with patch(
            "app.modules.goals.repository.GoalRepository.create",
            side_effect=rls_error,
        ):
            res = client.post("/api/v1/goals", json=_feasible_payload())

        assert res.status_code == 403, f"Expected 403, got {res.status_code}: {res.text}"
        body = res.json()
        assert "error" in body

    def test_check_constraint_violation_returns_400(self):
        """DB check-constraint violation caused by bad data -> 400."""
        check_err = _make_api_error(
            "23514",
            'new row for relation "goals" violates check constraint "goals_feasibility_status_check"',
        )
        with patch(
            "app.modules.goals.repository.GoalRepository.create",
            side_effect=check_err,
        ):
            res = client.post("/api/v1/goals", json=_feasible_payload())

        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        body = res.json()
        assert "error" in body

    def test_not_null_violation_returns_400(self):
        """DB not-null violation -> 400."""
        nn_err = _make_api_error(
            "23502",
            'null value in column "name" of relation "goals" violates not-null constraint',
        )
        with patch(
            "app.modules.goals.repository.GoalRepository.create",
            side_effect=nn_err,
        ):
            res = client.post("/api/v1/goals", json=_feasible_payload())

        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"

    def test_unique_violation_returns_400(self):
        """DB unique-key violation -> 400."""
        uniq_err = _make_api_error("23505", 'duplicate key value violates unique constraint "goals_pkey"')
        with patch("app.modules.goals.repository.GoalRepository.create", side_effect=uniq_err):
            res = client.post("/api/v1/goals", json=_feasible_payload())
        assert res.status_code == 400

    def test_unknown_db_error_remains_500(self):
        """
        Unknown PostgREST/Postgres code must NOT be silenced into 400/403.
        Real programming bugs (wrong column name, bad type, etc.) must remain 500
        so they stay visible in logs and trigger investigation.
        """
        unknown_err = _make_api_error(
            "PGRST999",
            "Something went wrong internally",
        )
        with patch(
            "app.modules.goals.repository.GoalRepository.create",
            side_effect=unknown_err,
        ):
            res = client.post("/api/v1/goals", json=_feasible_payload())

        assert res.status_code == 500, f"Expected 500, got {res.status_code}: {res.text}"


class TestGoalCreationRegressionGuard:
    """Ensure the changes did not break normal goal creation."""

    def test_successful_goal_creation_still_returns_201(self):
        """Happy-path regression: valid goal creation must still return 201."""
        with patch(
            "app.modules.goals.repository.GoalRepository.create",
            return_value=FAKE_ROW,
        ):
            res = client.post("/api/v1/goals", json=_feasible_payload())

        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        body = res.json()
        assert body["id"] == "goal-err-1"
        assert body["feasibility_status"] == "feasible"

    def test_infeasible_goal_still_blocked_with_422(self):
        """Infeasible goals must still be blocked."""
        res = client.post(
            "/api/v1/goals",
            json=_feasible_payload(monthly_contribution=50),
        )
        assert res.status_code == 422
        assert "feasibility" in res.json()

    def test_missing_auth_still_returns_401(self):
        """Unauthenticated requests must still be rejected before reaching the DB."""
        app.dependency_overrides.clear()
        res = client.post("/api/v1/goals", json=_feasible_payload())
        assert res.status_code == 401


class TestNoSensitiveDataInErrorResponses:
    """Confirm that no sensitive DB internals are ever exposed to callers."""

    def test_jwt_error_response_body_is_safe(self):
        jwt_error = _make_api_error(
            "PGRST301",
            "No suitable key or wrong key type",
            "None of the keys was able to decode the JWT",
        )
        with patch("app.modules.goals.repository.GoalRepository.create", side_effect=jwt_error):
            res = client.post("/api/v1/goals", json=_feasible_payload())

        body_str = res.text
        for forbidden in ["PGRST301", "eyJ", "decode", "jwt", "JWT"]:
            assert forbidden not in body_str, (
                f"Sensitive word '{forbidden}' found in error response: {body_str}"
            )

    def test_rls_error_response_body_is_safe(self):
        rls_error = _make_api_error(
            "42501",
            "new row violates row-level security policy",
        )
        with patch("app.modules.goals.repository.GoalRepository.create", side_effect=rls_error):
            res = client.post("/api/v1/goals", json=_feasible_payload())

        body_str = res.text
        for forbidden in ["42501", "row-level security", "policy"]:
            assert forbidden not in body_str, (
                f"Sensitive word '{forbidden}' found in error response: {body_str}"
            )

    def test_unknown_error_response_body_is_safe(self):
        unknown_err = _make_api_error("PGRST999", "internal_db_secret_detail")
        with patch("app.modules.goals.repository.GoalRepository.create", side_effect=unknown_err):
            res = client.post("/api/v1/goals", json=_feasible_payload())

        body_str = res.text
        assert "internal_db_secret_detail" not in body_str
        assert "PGRST999" not in body_str
