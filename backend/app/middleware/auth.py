from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.exceptions import AppError
from app.modules.auth.service import AuthService
from app.modules.auth.schemas import UserOut

bearer_scheme = HTTPBearer(auto_error=False)


async def get_access_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    if credentials is None:
        raise AppError("Missing or malformed Authorization header", 401)
    return credentials.credentials


async def get_current_user(token: str = Depends(get_access_token)) -> UserOut:
    """FastAPI dependency — use `user: UserOut = Depends(get_current_user)`
    on any route that needs a logged-in user, same role authGuard played
    in the Node version, just injected per-route instead of mounted globally."""
    return AuthService.get_current_user(token)