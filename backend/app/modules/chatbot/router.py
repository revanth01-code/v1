from fastapi import APIRouter, Depends
from app.middleware.auth import get_current_user, get_access_token
from app.modules.auth.schemas import UserOut
from .schemas import ChatRequest, ChatResponse
from .service import ChatbotService

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


@router.post("/message", response_model=ChatResponse)
def send_message(
    payload: ChatRequest,
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    reply = ChatbotService.send_message(token, user.id, payload)
    return ChatResponse(reply=reply)