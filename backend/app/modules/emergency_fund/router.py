from fastapi import APIRouter, Depends, status
from app.middleware.auth import get_current_user, get_access_token
from app.modules.auth.schemas import UserOut
from .schemas import EmergencyFundCreate, EmergencyFundOut, EmergencyFundUpdate
from .service import EmergencyFundService

router = APIRouter(prefix="/emergency-fund", tags=["emergency-fund"])


@router.post("", response_model=EmergencyFundOut, status_code=status.HTTP_201_CREATED)
def create_emergency_fund(
    payload: EmergencyFundCreate,
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    return EmergencyFundService.create(token, user.id, payload)


@router.get("", response_model=EmergencyFundOut)
def get_emergency_fund(
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    return EmergencyFundService.get(token, user.id)


@router.put("", response_model=EmergencyFundOut)
def update_emergency_fund(
    payload: EmergencyFundUpdate,
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    return EmergencyFundService.update(token, user.id, payload)