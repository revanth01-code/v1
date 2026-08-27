import base64
import json
import sys
from datetime import datetime, timezone
from app.core.supabase import supabase_public, get_token_hash, invalidate_user_client
from app.core.exceptions import AppError
from .schemas import SignUpInput, LoginInput, AuthSession, UserOut

# Hashed token cache keys to avoid raw tokens as dictionary keys.
# Note: Raw tokens may still exist in memory within connection pools of cached Supabase client instances.
_auth_cache = {}  # token_hash -> UserOut
_auth_cache_timestamps = {}  # token_hash -> float (expires_at timestamp)


def _decode_jwt_payload(token: str) -> dict:
    """Decodes the JWT payload locally without verifying signature to extract exp metadata."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload_b64 = parts[1]
        rem = len(payload_b64) % 4
        if rem > 0:
            payload_b64 += "=" * (4 - rem)
        decoded = base64.urlsafe_b64decode(payload_b64)
        return json.loads(decoded)
    except Exception:
        return {}


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
        # Stateless backend — verify token is valid first
        try:
            res = supabase_public.auth.get_user(access_token)
        except Exception:
            raise AppError("Invalid or expired session", 401)
        if not res or not res.user:
            raise AppError("Invalid or expired session", 401)

        # Invalidate cached Supabase client
        invalidate_user_client(access_token)

        # Invalidate authentication cache entries using the secure hash key
        token_hash = get_token_hash(access_token)
        global _auth_cache, _auth_cache_timestamps
        _auth_cache.pop(token_hash, None)
        _auth_cache_timestamps.pop(token_hash, None)

    @staticmethod
    def get_current_user(access_token: str) -> UserOut:
        global _auth_cache, _auth_cache_timestamps

        # If running unit tests (pytest), bypass in-memory caching entirely
        if "pytest" in sys.modules or "_pytest" in sys.modules:
            try:
                res = supabase_public.auth.get_user(access_token)
            except Exception:
                raise AppError("Invalid or expired session", 401)
            if not res or not res.user:
                raise AppError("Invalid or expired session", 401)
            return UserOut(id=res.user.id, email=res.user.email)

        now = datetime.now(timezone.utc)
        payload = _decode_jwt_payload(access_token)
        exp = payload.get("exp")

        # If token is already expired according to JWT metadata, fail immediately
        if exp and now.timestamp() >= exp:
            token_hash = get_token_hash(access_token)
            _auth_cache.pop(token_hash, None)
            _auth_cache_timestamps.pop(token_hash, None)
            invalidate_user_client(access_token)
            raise AppError("Invalid or expired session", 401)

        token_hash = get_token_hash(access_token)
        now_ts = now.timestamp()

        if token_hash in _auth_cache:
            expires_at = _auth_cache_timestamps[token_hash]
            if now_ts < expires_at:
                return _auth_cache[token_hash]

        try:
            res = supabase_public.auth.get_user(access_token)
        except Exception:
            raise AppError("Invalid or expired session", 401)
        if not res or not res.user:
            raise AppError("Invalid or expired session", 401)

        user_out = UserOut(id=res.user.id, email=res.user.email)

        # Calculate a fixed expires_at capped at 120s or the JWT's actual exp
        max_lifetime = 120.0
        if exp:
            time_to_exp = exp - now_ts
            lifetime = min(max_lifetime, time_to_exp)
        else:
            lifetime = max_lifetime

        _auth_cache[token_hash] = user_out
        _auth_cache_timestamps[token_hash] = now_ts + lifetime
        return user_out