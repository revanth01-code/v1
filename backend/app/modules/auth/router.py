from fastapi import APIRouter, Depends, status, Request
from app.middleware.auth import get_current_user, get_access_token
from .schemas import SignUpInput, LoginInput, UserOut
from .service import AuthService
from app.core.limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def sign_up(request: Request, payload: SignUpInput):
    session = AuthService.sign_up(payload)
    return {"session": session}


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, payload: LoginInput):
    session = AuthService.login(payload)
    return {"session": session}


@router.post("/logout")
def logout(token: str = Depends(get_access_token)):
    AuthService.logout(token)
    return {"message": "Logged out"}


@router.get("/me")
def me(user: UserOut = Depends(get_current_user)):
    return {"user": user}