from app.core.supabase import supabase_public
from app.core.exceptions import AppError
from .schemas import SignUpInput, LoginInput, AuthSession, UserOut


def _to_session(auth_response) -> AuthSession:
    session = auth_response.session
    user = auth_response.user
    if not session or not user:
        raise AppError(
            "Sign-in did not return a session — check email confirmation settings",
            500,
        )
    return AuthSession(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_at=session.expires_at,
        user=UserOut(id=user.id, email=user.email),
    )


class AuthService:
    @staticmethod
    def sign_up(payload: SignUpInput) -> AuthSession:
        try:
            res = supabase_public.auth.sign_up(
                {"email": payload.email, "password": payload.password}
            )
        except Exception as e:
            raise AppError(str(e), 400)

        if not res.session:
            raise AppError(
                "Account created — check your email to confirm before logging in.",
                202,
            )
        return _to_session(res)

    @staticmethod
    def login(payload: LoginInput) -> AuthSession:
        try:
            res = supabase_public.auth.sign_in_with_password(
                {"email": payload.email, "password": payload.password}
            )
        except Exception:
            raise AppError("Invalid email or password", 401)
        return _to_session(res)

    @staticmethod
    def logout(access_token: str) -> None:
        # Stateless backend — nothing server-side to revoke. We just verify
        # the token is still valid so a bad token returns a real error
        # instead of a fake 200.
        try:
            res = supabase_public.auth.get_user(access_token)
        except Exception:
            raise AppError("Invalid or expired session", 401)
        if not res or not res.user:
            raise AppError("Invalid or expired session", 401)

    @staticmethod
    def get_current_user(access_token: str) -> UserOut:
        try:
            res = supabase_public.auth.get_user(access_token)
        except Exception:
            raise AppError("Invalid or expired session", 401)
        if not res or not res.user:
            raise AppError("Invalid or expired session", 401)
        return UserOut(id=res.user.id, email=res.user.email)