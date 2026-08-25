from fastapi import APIRouter, Depends, status
from app.middleware.auth import get_current_user, get_access_token
from app.modules.auth.schemas import UserOut
from .schemas import ProfileCreate, ProfileUpdate, ProfileOut
from .service import ProfileService

router = APIRouter(prefix="/profile", tags=["profile"])


@router.post("", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
def create_profile(
    payload: ProfileCreate,
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    return ProfileService.create_profile(token, user.id, payload)


@router.get("", response_model=ProfileOut)
def get_profile(
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    return ProfileService.get_profile(token, user.id)


@router.put("", response_model=ProfileOut)
def update_profile(
    payload: ProfileUpdate,
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    return ProfileService.update_profile(token, user.id, payload)