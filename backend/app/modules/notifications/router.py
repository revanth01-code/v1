from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings
from app.core.exceptions import AppError
from .schemas import SIPRemindersResponse, GoalProgressRemindersResponse
from .service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])

_bearer_scheme = HTTPBearer(auto_error=False)


def _require_notification_key(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> None:
    """Server-to-server dependency.
    Validates the incoming Bearer token against NOTIFICATION_API_KEY.
    Rejects with 401 when the key is missing or wrong.
    Rejects with 503 when the server has not configured the key at all
    (prevents accidental open access in misconfigured deployments).
    """
    if not settings.NOTIFICATION_API_KEY:
        raise AppError(
            "Notification API key is not configured on this server.", 503
        )
    if credentials is None or credentials.credentials != settings.NOTIFICATION_API_KEY:
        raise AppError("Invalid or missing notification API key.", 401)


@router.get(
    "/sip-reminders",
    response_model=SIPRemindersResponse,
    summary="SIP reminder data for n8n",
    description=(
        "Server-to-server endpoint.  Returns the minimal list of SIP-enabled "
        "goals and their associated user email addresses so that n8n can decide "
        "which reminders to send today via Resend.  "
        "Requires Authorization: Bearer <NOTIFICATION_API_KEY>."
    ),
)
def get_sip_reminders(
    _: None = Depends(_require_notification_key),
) -> SIPRemindersResponse:
    return NotificationService.get_sip_reminders()


@router.get(
    "/goal-progress",
    response_model=GoalProgressRemindersResponse,
    summary="Goal progress milestone data for n8n",
    description=(
        "Server-to-server endpoint. Returns goals that have reached a progress "
        "milestone (25%, 50%, 75%, 100%) and their associated user email addresses, "
        "so that n8n can decide which notifications to send. "
        "Requires Authorization: Bearer <NOTIFICATION_API_KEY>."
    ),
)
def get_goal_progress(
    _: None = Depends(_require_notification_key),
) -> GoalProgressRemindersResponse:
    return NotificationService.get_goal_progress_reminders()
