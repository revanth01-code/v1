from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.core.supabase import supabase_public

client = TestClient(app)

FAKE_SESSION = SimpleNamespace(
    access_token="fake-access-token",
    refresh_token="fake-refresh-token",
    expires_at=9999999999,
)
FAKE_USER = SimpleNamespace(id="user-123", email="test@example.com")


def fake_auth_response(session, user):
    return SimpleNamespace(session=session, user=user)


class TestSignUp:
    def test_invalid_email_returns_422(self):
        res = client.post("/api/v1/auth/signup", json={"email": "not-an-email", "password": "password123"})
        assert res.status_code == 422

    def test_short_password_returns_422(self):
        res = client.post("/api/v1/auth/signup", json={"email": "test@example.com", "password": "short"})
        assert res.status_code == 422

    def test_success_returns_201(self):
        with patch.object(supabase_public.auth, "sign_up", return_value=fake_auth_response(FAKE_SESSION, FAKE_USER)):
            res = client.post("/api/v1/auth/signup", json={"email": "test@example.com", "password": "password123"})
        assert res.status_code == 201
        assert res.json()["session"]["access_token"] == "fake-access-token"

    def test_no_session_returns_202(self):
        with patch.object(supabase_public.auth, "sign_up", return_value=fake_auth_response(None, FAKE_USER)):
            res = client.post("/api/v1/auth/signup", json={"email": "test@example.com", "password": "password123"})
        assert res.status_code == 202

    def test_duplicate_email_returns_400(self):
        with patch.object(supabase_public.auth, "sign_up", side_effect=Exception("User already registered")):
            res = client.post("/api/v1/auth/signup", json={"email": "test@example.com", "password": "password123"})
        assert res.status_code == 400


class TestLogin:
    def test_success_returns_200(self):
        with patch.object(supabase_public.auth, "sign_in_with_password", return_value=fake_auth_response(FAKE_SESSION, FAKE_USER)):
            res = client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "password123"})
        assert res.status_code == 200

    def test_invalid_credentials_returns_401(self):
        with patch.object(supabase_public.auth, "sign_in_with_password", side_effect=Exception("Invalid login credentials")):
            res = client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "wrong"})
        assert res.status_code == 401


class TestMe:
    def test_no_header_returns_401(self):
        res = client.get("/api/v1/auth/me")
        assert res.status_code == 401

    def test_invalid_token_returns_401(self):
        with patch.object(supabase_public.auth, "get_user", side_effect=Exception("invalid token")):
            res = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer bad-token"})
        assert res.status_code == 401

    def test_valid_token_returns_200(self):
        with patch.object(supabase_public.auth, "get_user", return_value=SimpleNamespace(user=FAKE_USER)):
            res = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer good-token"})
        assert res.status_code == 200
        assert res.json()["user"]["id"] == "user-123"


class TestLogout:
    def test_valid_token_returns_200(self):
        with patch.object(supabase_public.auth, "get_user", return_value=SimpleNamespace(user=FAKE_USER)):
            res = client.post("/api/v1/auth/logout", headers={"Authorization": "Bearer good-token"})
        assert res.status_code == 200