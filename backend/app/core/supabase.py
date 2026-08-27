import sys
import hashlib
from datetime import datetime, timezone
from supabase import create_client, Client
from app.core.config import settings

# Bypasses RLS — only for trusted server-side operations across users.
supabase_admin: Client = create_client(
    settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
)

# Used for auth calls (signup/login/get_user).
supabase_public: Client = create_client(
    settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY
)

_user_clients = {}  # token_hash -> {"client": Client, "expires_at": float}
CLIENT_TTL_SECONDS = 300
MAX_CLIENTS_CACHE_SIZE = 500


def get_token_hash(token: str) -> str:
    """Returns a SHA-256 hash of the token for use as a secure cache dictionary key.
    Note: Hashing is used to avoid storing raw tokens as keys, but the raw token may still
    internally remain in memory within the instantiated Supabase Client headers/connection pools."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def supabase_as_user(access_token: str) -> Client:
    """RLS-scoped client acting as the given user. Used from Module 2
    onward for queries against user-owned tables. Reuses client instances
    to prevent httpx connection pool creation overhead on every query."""
    global _user_clients

    # If running unit tests (pytest), bypass in-memory caching entirely
    if "pytest" in sys.modules or "_pytest" in sys.modules:
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
        client.postgrest.auth(access_token)
        return client

    token_hash = get_token_hash(access_token)
    now = datetime.now(timezone.utc).timestamp()

    # Lazy cleanup of expired entries
    expired_keys = [k for k, v in _user_clients.items() if now >= v["expires_at"]]
    for k in expired_keys:
        _user_clients.pop(k, None)

    if token_hash in _user_clients:
        entry = _user_clients[token_hash]
        if now < entry["expires_at"]:
            return entry["client"]

    # Enforce maximum cache size by removing the oldest half
    if len(_user_clients) >= MAX_CLIENTS_CACHE_SIZE:
        sorted_keys = sorted(_user_clients.keys(), key=lambda k: _user_clients[k]["expires_at"])
        for k in sorted_keys[:len(sorted_keys) // 2]:
            _user_clients.pop(k, None)

    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.postgrest.auth(access_token)
    _user_clients[token_hash] = {
        "client": client,
        "expires_at": now + CLIENT_TTL_SECONDS
    }
    return client


def invalidate_user_client(access_token: str) -> None:
    """Removes a user's cached client on logout or session invalidation."""
    global _user_clients
    token_hash = get_token_hash(access_token)
    _user_clients.pop(token_hash, None)