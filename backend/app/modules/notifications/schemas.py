from pydantic import BaseModel
from typing import Optional


class SIPReminderItem(BaseModel):
    """Minimal data shape returned per SIP-enabled goal for n8n notifications.
    Intentionally narrow — do NOT add financial/feasibility fields here."""
    user_id: str
    email: Optional[str]
    goal_id: str
    goal_name: str
    monthly_contribution: float
    sip_day: int


class SIPRemindersResponse(BaseModel):
    reminders: list[SIPReminderItem]
