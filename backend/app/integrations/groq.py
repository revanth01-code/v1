import httpx
from app.core.config import settings
from app.core.constants import GROQ_API_URL, GROQ_MODEL
from app.core.exceptions import AppError


def get_chat_completion(messages: list[dict], max_tokens: int = 600) -> str:
    if not settings.GROQ_API_KEY:
        raise AppError("Chatbot is not configured — GROQ_API_KEY is missing.", 503)

    try:
        resp = httpx.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.3,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise AppError(f"Chatbot service error: {e}", 502)

    data = resp.json()
    return data["choices"][0]["message"]["content"]