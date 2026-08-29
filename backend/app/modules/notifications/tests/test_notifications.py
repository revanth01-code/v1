import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)

TEST_KEY = "test-notification-secret-key"

# ── Fake data mirrors what NotificationRepository returns ─────────────────────

FAKE_GOAL_WITH_SIP = {
    "id": "goal-sip-1",
    "user_id": "user-abc",
    "name": "Vacation Fund",
    "monthly_contribution": 5000.0,
    "sip_day": 5,
}

FAKE_GOAL_NO_SIP = {
    "id": "goal-no-sip-1",
    "user_id": "user-xyz",
    "name": "Car Fund",
    "monthly_contribution": 10000.0,
    "sip_day": None,  # Should never come back from the repo — but guards against bugs
}

FAKE_USER_EMAIL = "investor@example.com"


# ── Helper ─────────────────────────────────────────────────────────────────────

def auth_header(key: str = TEST_KEY) -> dict:
    return {"Authorization": f"Bearer {key}"}


# ── Auth rejection tests ───────────────────────────────────────────────────────

class TestNotificationAuth:
    def test_rejects_missing_auth_header(self, monkeypatch):
        monkeypatch.setattr(settings, "NOTIFICATION_API_KEY", TEST_KEY)
        res = client.get("/api/v1/notifications/sip-reminders")
        assert res.status_code == 401

    def test_rejects_wrong_key(self, monkeypatch):
        monkeypatch.setattr(settings, "NOTIFICATION_API_KEY", TEST_KEY)
        res = client.get(
            "/api/v1/notifications/sip-reminders",
            headers=auth_header("completely-wrong-key"),
        )
        assert res.status_code == 401

    def test_rejects_when_key_not_configured(self, monkeypatch):
        """When NOTIFICATION_API_KEY is blank the server must return 503
        to prevent accidental open access in a misconfigured deployment."""
        monkeypatch.setattr(settings, "NOTIFICATION_API_KEY", "")
        res = client.get(
            "/api/v1/notifications/sip-reminders",
            headers=auth_header(TEST_KEY),
        )
        assert res.status_code == 503


# ── Functional tests ───────────────────────────────────────────────────────────

class TestSIPRemindersEndpoint:
    def test_valid_key_returns_200(self, monkeypatch):
        monkeypatch.setattr(settings, "NOTIFICATION_API_KEY", TEST_KEY)
        with (
            patch(
                "app.modules.notifications.repository.NotificationRepository.list_sip_goals",
                return_value=[],
            ),
        ):
            res = client.get(
                "/api/v1/notifications/sip-reminders",
                headers=auth_header(),
            )
        assert res.status_code == 200
        assert res.json() == {"reminders": []}

    def test_includes_sip_goals_with_correct_fields(self, monkeypatch):
        monkeypatch.setattr(settings, "NOTIFICATION_API_KEY", TEST_KEY)
        with (
            patch(
                "app.modules.notifications.repository.NotificationRepository.list_sip_goals",
                return_value=[FAKE_GOAL_WITH_SIP],
            ),
            patch(
                "app.modules.notifications.repository.NotificationRepository.get_user_email",
                return_value=FAKE_USER_EMAIL,
            ),
        ):
            res = client.get(
                "/api/v1/notifications/sip-reminders",
                headers=auth_header(),
            )

        assert res.status_code == 200
        reminders = res.json()["reminders"]
        assert len(reminders) == 1

        item = reminders[0]
        assert item["user_id"] == "user-abc"
        assert item["email"] == FAKE_USER_EMAIL
        assert item["goal_id"] == "goal-sip-1"
        assert item["goal_name"] == "Vacation Fund"
        assert item["monthly_contribution"] == 5000.0
        assert item["sip_day"] == 5

    def test_response_contains_only_notification_fields(self, monkeypatch):
        """Ensure no extra financial/feasibility data leaks into the response."""
        monkeypatch.setattr(settings, "NOTIFICATION_API_KEY", TEST_KEY)
        with (
            patch(
                "app.modules.notifications.repository.NotificationRepository.list_sip_goals",
                return_value=[FAKE_GOAL_WITH_SIP],
            ),
            patch(
                "app.modules.notifications.repository.NotificationRepository.get_user_email",
                return_value=FAKE_USER_EMAIL,
            ),
        ):
            res = client.get(
                "/api/v1/notifications/sip-reminders",
                headers=auth_header(),
            )

        item = res.json()["reminders"][0]
        allowed_keys = {"user_id", "email", "goal_id", "goal_name", "monthly_contribution", "sip_day"}
        assert set(item.keys()) == allowed_keys

    def test_goals_without_sip_excluded_by_repo_filter(self, monkeypatch):
        """The repository query filters for sip_day NOT NULL.  If it returns
        no rows, the endpoint returns an empty list."""
        monkeypatch.setattr(settings, "NOTIFICATION_API_KEY", TEST_KEY)
        with patch(
            "app.modules.notifications.repository.NotificationRepository.list_sip_goals",
            return_value=[],  # repo already filtered — empty result
        ):
            res = client.get(
                "/api/v1/notifications/sip-reminders",
                headers=auth_header(),
            )
        assert res.status_code == 200
        assert res.json()["reminders"] == []

    def test_multiple_goals_multiple_users(self, monkeypatch):
        monkeypatch.setattr(settings, "NOTIFICATION_API_KEY", TEST_KEY)
        goal_a = {**FAKE_GOAL_WITH_SIP, "id": "g-a", "user_id": "u-1", "sip_day": 1}
        goal_b = {**FAKE_GOAL_WITH_SIP, "id": "g-b", "user_id": "u-2", "name": "Retirement", "sip_day": 28}

        def fake_email(uid):
            return f"{uid}@example.com"

        with (
            patch(
                "app.modules.notifications.repository.NotificationRepository.list_sip_goals",
                return_value=[goal_a, goal_b],
            ),
            patch(
                "app.modules.notifications.repository.NotificationRepository.get_user_email",
                side_effect=fake_email,
            ),
        ):
            res = client.get(
                "/api/v1/notifications/sip-reminders",
                headers=auth_header(),
            )

        reminders = res.json()["reminders"]
        assert len(reminders) == 2
        assert reminders[0]["sip_day"] == 1
        assert reminders[1]["sip_day"] == 28
        assert reminders[0]["email"] == "u-1@example.com"
        assert reminders[1]["email"] == "u-2@example.com"

    def test_email_cache_reused_for_same_user(self, monkeypatch):
        """When two goals share the same user_id, get_user_email should be
        called exactly once (email cached per request)."""
        monkeypatch.setattr(settings, "NOTIFICATION_API_KEY", TEST_KEY)
        same_user_goals = [
            {**FAKE_GOAL_WITH_SIP, "id": "g-1", "user_id": "u-shared"},
            {**FAKE_GOAL_WITH_SIP, "id": "g-2", "user_id": "u-shared", "sip_day": 10},
        ]

        with (
            patch(
                "app.modules.notifications.repository.NotificationRepository.list_sip_goals",
                return_value=same_user_goals,
            ),
            patch(
                "app.modules.notifications.repository.NotificationRepository.get_user_email",
                return_value="shared@example.com",
            ) as mock_email,
        ):
            res = client.get(
                "/api/v1/notifications/sip-reminders",
                headers=auth_header(),
            )

        assert res.status_code == 200
        assert len(res.json()["reminders"]) == 2
        # Email fetch called only once despite two goals for the same user
        mock_email.assert_called_once_with("u-shared")
