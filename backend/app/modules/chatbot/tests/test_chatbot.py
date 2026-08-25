import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.core.exceptions import AppError
from app.middleware.auth import get_current_user, get_access_token
from app.modules.auth.schemas import UserOut

client = TestClient(app)
FAKE_USER = UserOut(id="user-123", email="test@example.com")


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[get_access_token] = lambda: "fake-token"
    yield
    app.dependency_overrides.clear()


class TestSendMessage:
    def test_requires_auth(self):
        app.dependency_overrides.clear()
        res = client.post("/api/v1/chatbot/message", json={"messages": [{"role": "user", "content": "hi"}]})
        assert res.status_code == 401

    def test_rejects_empty_messages(self):
        res = client.post("/api/v1/chatbot/message", json={"messages": []})
        assert res.status_code == 422

    def test_returns_reply_on_success(self):
        with patch("app.modules.chatbot.service.build_user_context", return_value={"profile": None, "goals": []}), \
             patch("app.modules.chatbot.service.groq.get_chat_completion", return_value="Here's my answer.") as mock_groq:
            res = client.post(
                "/api/v1/chatbot/message",
                json={"messages": [{"role": "user", "content": "How am I doing on my goals?"}]},
            )
        assert res.status_code == 200
        assert res.json()["reply"] == "Here's my answer."
        mock_groq.assert_called_once()

    def test_system_prompt_includes_actual_user_context(self):
        fake_context = {"profile": {"monthly_income": 80000}, "goals": [{"name": "Car"}]}
        with patch("app.modules.chatbot.service.build_user_context", return_value=fake_context), \
             patch("app.modules.chatbot.service.groq.get_chat_completion", return_value="ok") as mock_groq:
            client.post(
                "/api/v1/chatbot/message",
                json={"messages": [{"role": "user", "content": "hi"}]},
            )
        sent_messages = mock_groq.call_args[0][0]
        system_message = sent_messages[0]
        assert system_message["role"] == "system"
        assert "80000" in system_message["content"]
        assert "Car" in system_message["content"]

    def test_trims_long_history_to_max_messages(self):
        long_history = [{"role": "user", "content": f"message {i}"} for i in range(30)]
        with patch("app.modules.chatbot.service.build_user_context", return_value={}), \
             patch("app.modules.chatbot.service.groq.get_chat_completion", return_value="ok") as mock_groq:
            client.post("/api/v1/chatbot/message", json={"messages": long_history})
        sent_messages = mock_groq.call_args[0][0]
        # 1 system message + at most MAX_HISTORY_MESSAGES (20) history messages
        assert len(sent_messages) <= 21

    def test_returns_503_when_groq_key_missing(self):
        with patch("app.modules.chatbot.service.build_user_context", return_value={}), \
             patch("app.modules.chatbot.service.groq.get_chat_completion",
                   side_effect=AppError("Chatbot is not configured — GROQ_API_KEY is missing.", 503)):
            res = client.post("/api/v1/chatbot/message", json={"messages": [{"role": "user", "content": "hi"}]})
        assert res.status_code == 503


class TestContextBuilder:
    def test_degrades_gracefully_when_modules_missing(self):
        """If profile/goals/retirement/emergency_fund all raise (nothing set
        up yet), context builder should return safe defaults, not crash."""
        from app.modules.chatbot.context_builder import build_user_context

        with patch("app.modules.chatbot.context_builder.ProfileService.get_profile",
                   side_effect=AppError("not found", 404)), \
             patch("app.modules.chatbot.context_builder.GoalService.list_goals", return_value=[]), \
             patch("app.modules.chatbot.context_builder.RetirementService.get",
                   side_effect=AppError("not found", 404)), \
             patch("app.modules.chatbot.context_builder.EmergencyFundService.get",
                   side_effect=AppError("not found", 404)):
            context = build_user_context("fake-token", "user-123")

        assert context["profile"] is None
        assert context["goals"] == []
        assert context["retirement"] is None
        assert context["emergency_fund"] is None