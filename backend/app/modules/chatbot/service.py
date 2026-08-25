import json
from app.integrations import groq
from .context_builder import build_user_context
from .schemas import ChatRequest

SYSTEM_PROMPT_TEMPLATE = """You are a financial coach embedded in a goal-based investment planning app.
Use the JSON context below — which reflects the user's ACTUAL saved data — to answer their question specifically and accurately.

Rules:
- Only use numbers that appear in the context below. Never invent or estimate a figure that isn't present.
- If the user asks about something not present in the context (e.g. no retirement plan saved yet), say so plainly and suggest they set it up, rather than guessing.
- Do not recommend specific funds to buy or sell — flag that this needs registered investment advice.
- Keep responses concise and conversational.

User's current data:
{context_json}
"""

# Bounds the prompt size even if the frontend sends a very long conversation.
MAX_HISTORY_MESSAGES = 20


class ChatbotService:
    @staticmethod
    def send_message(access_token: str, user_id: str, payload: ChatRequest) -> str:
        context = build_user_context(access_token, user_id)
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context_json=json.dumps(context, indent=2))

        trimmed_history = payload.messages[-MAX_HISTORY_MESSAGES:]
        groq_messages = [{"role": "system", "content": system_prompt}] + [
            {"role": m.role, "content": m.content} for m in trimmed_history
        ]

        return groq.get_chat_completion(groq_messages)