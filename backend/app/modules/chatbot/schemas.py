from typing import Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    # Full conversation history, sent by the frontend each time — nothing
    # is persisted server-side, per the stateless design decision.
    messages: list[ChatMessage] = Field(min_length=1)


class ChatResponse(BaseModel):
    reply: str