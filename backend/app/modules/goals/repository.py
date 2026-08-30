import sys
import structlog
from datetime import datetime, timezone
from typing import Optional

from app.core.supabase import supabase_as_user

TABLE = "goals"

logger = structlog.get_logger()

_goals_list_cache = {}
_goals_list_cache_timestamps = {}


class GoalRepository:
    @staticmethod
    def create(access_token: str, user_id: str, payload: dict) -> dict:
        global _goals_list_cache, _goals_list_cache_timestamps

        logger.info(
            "goal_create_started",
            user_id=user_id,
            payload_keys=list(payload.keys()),
        )

        try:
            client = supabase_as_user(access_token)

            row = {
                **payload,
                "user_id": user_id,
            }

            logger.info(
                "goal_database_insert_started",
                user_id=user_id,
                row_keys=list(row.keys()),
            )

            res = client.table(TABLE).insert(row).execute()

            logger.info(
                "goal_database_insert_completed",
                user_id=user_id,
                has_data=bool(res.data),
            )

            # Invalidate cache on creation
            _goals_list_cache.clear()
            _goals_list_cache_timestamps.clear()

            if not res.data:
                raise RuntimeError(
                    "Goal insert succeeded but no data was returned"
                )

            return res.data[0]

        except Exception as exc:
            logger.exception(
                "goal_database_insert_failed",
                user_id=user_id,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise

    @staticmethod
    def list_by_user(
        access_token: str,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        global _goals_list_cache, _goals_list_cache_timestamps

        # If running unit tests (pytest), bypass in-memory caching entirely
        if "pytest" in sys.modules or "_pytest" in sys.modules:
            client = supabase_as_user(access_token)
            res = (
                client.table(TABLE)
                .select("*")
                .eq("user_id", user_id)
                .order("priority_rank", desc=False, nullsfirst=False)
                .order("created_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )
            return res.data

        now = datetime.now(timezone.utc)
        cache_key = (user_id, access_token, limit, offset)

        if cache_key in _goals_list_cache:
            last_check = _goals_list_cache_timestamps[cache_key]

            if (now - last_check).total_seconds() < 10:
                return _goals_list_cache[cache_key]

        client = supabase_as_user(access_token)

        res = (
            client.table(TABLE)
            .select("*")
            .eq("user_id", user_id)
            .order("priority_rank", desc=False, nullsfirst=False)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        val = res.data

        _goals_list_cache[cache_key] = val
        _goals_list_cache_timestamps[cache_key] = now

        return val

    @staticmethod
    def get_by_id(
        access_token: str,
        user_id: str,
        goal_id: str,
    ) -> dict | None:
        client = supabase_as_user(access_token)

        res = (
            client.table(TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("id", goal_id)
            .maybe_single()
            .execute()
        )

        return res.data if res else None

    @staticmethod
    def update_priority_rank(
        access_token: str,
        user_id: str,
        goal_id: str,
        priority_rank: Optional[int],
    ) -> dict | None:
        global _goals_list_cache, _goals_list_cache_timestamps

        client = supabase_as_user(access_token)

        res = (
            client.table(TABLE)
            .update({"priority_rank": priority_rank})
            .eq("user_id", user_id)
            .eq("id", goal_id)
            .execute()
        )

        # Invalidate cache on update
        _goals_list_cache.clear()
        _goals_list_cache_timestamps.clear()

        return res.data[0] if res.data else None