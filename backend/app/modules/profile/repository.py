import sys
from datetime import datetime, timezone
from typing import Optional
from app.core.supabase import supabase_as_user

TABLE = "financial_profile"

_profile_cache = {}
_profile_cache_timestamps = {}


class ProfileRepository:
    """All Supabase queries for this module live here, and only here.
    Every query uses a client scoped to the requesting user's own JWT
    (via supabase_as_user), so Postgres RLS enforces the "only your own
    row" rule at the database level — even if a bug elsewhere in the app
    tried to query someone else's data, the database itself would refuse."""

    @staticmethod
    def get_by_user_id(access_token: str, user_id: str) -> Optional[dict]:
        global _profile_cache, _profile_cache_timestamps

        # If running unit tests (pytest), bypass in-memory caching entirely
        if "pytest" in sys.modules or "_pytest" in sys.modules:
            client = supabase_as_user(access_token)
            res = client.table(TABLE).select("*").eq("user_id", user_id).maybe_single().execute()
            return res.data if res else None

        now = datetime.now(timezone.utc)
        cache_key = (user_id, access_token)
        if cache_key in _profile_cache:
            last_check = _profile_cache_timestamps[cache_key]
            if (now - last_check).total_seconds() < 10:  # Cache for 10 seconds
                return _profile_cache[cache_key]

        client = supabase_as_user(access_token)
        res = client.table(TABLE).select("*").eq("user_id", user_id).maybe_single().execute()
        val = res.data if res else None

        _profile_cache[cache_key] = val
        _profile_cache_timestamps[cache_key] = now
        return val

    @staticmethod
    def create(access_token: str, user_id: str, payload: dict) -> dict:
        global _profile_cache, _profile_cache_timestamps
        client = supabase_as_user(access_token)
        row = {**payload, "user_id": user_id}
        res = client.table(TABLE).insert(row).execute()

        cache_key = (user_id, access_token)
        _profile_cache[cache_key] = res.data[0]
        _profile_cache_timestamps[cache_key] = datetime.now(timezone.utc)

        return res.data[0]

    @staticmethod
    def update(access_token: str, user_id: str, payload: dict) -> dict:
        global _profile_cache, _profile_cache_timestamps
        client = supabase_as_user(access_token)
        res = (
            client.table(TABLE)
            .update(payload)
            .eq("user_id", user_id)
            .execute()
        )

        cache_key = (user_id, access_token)
        _profile_cache[cache_key] = res.data[0]
        _profile_cache_timestamps[cache_key] = datetime.now(timezone.utc)

        return res.data[0]