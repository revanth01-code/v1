from fastapi import APIRouter, Depends
from app.middleware.auth import get_current_user, get_access_token
from app.modules.auth.schemas import UserOut
from .schemas import DashboardOut
from .service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def get_dashboard(
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    return DashboardService.get_summary(token, user.id)