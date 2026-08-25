from fastapi import APIRouter, Depends, Request
from app.middleware.auth import get_current_user, get_access_token
from app.modules.auth.schemas import UserOut
from .schemas import ChatRequest, ChatResponse
from .service import ChatbotService
from app.core.limiter import limiter

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


@router.post("/message", response_model=ChatResponse)
@limiter.limit("20/minute")
def send_message(
    request: Request,
    payload: ChatRequest,
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    reply = ChatbotService.send_message(token, user.id, payload)
    return ChatResponse(reply=reply)