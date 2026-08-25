from fastapi import APIRouter, Depends, status
from app.middleware.auth import get_current_user, get_access_token
from .schemas import SignUpInput, LoginInput, UserOut
from .service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def sign_up(payload: SignUpInput):
    session = AuthService.sign_up(payload)
    return {"session": session}


@router.post("/login")
def login(payload: LoginInput):
    session = AuthService.login(payload)
    return {"session": session}


@router.post("/logout")
def logout(token: str = Depends(get_access_token)):
    AuthService.logout(token)
    return {"message": "Logged out"}


@router.get("/me")
def me(user: UserOut = Depends(get_current_user)):
    return {"user": user}