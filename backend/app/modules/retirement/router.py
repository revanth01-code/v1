from fastapi import APIRouter, Depends, status
from app.middleware.auth import get_current_user, get_access_token
from app.modules.auth.schemas import UserOut
from .schemas import RetirementCreate, RetirementOut, RetirementUpdate
from .service import RetirementService

router = APIRouter(prefix="/retirement", tags=["retirement"])


@router.post("", response_model=RetirementOut, status_code=status.HTTP_201_CREATED)
def create_retirement_plan(
    payload: RetirementCreate,
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    return RetirementService.create(token, user.id, payload)


@router.get("", response_model=RetirementOut)
def get_retirement_plan(
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    return RetirementService.get(token, user.id)


@router.put("", response_model=RetirementOut)
def update_retirement_plan(
    payload: RetirementUpdate,
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    return RetirementService.update(token, user.id, payload)