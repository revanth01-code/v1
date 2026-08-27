from typing import Optional
from app.core.supabase import supabase_as_user

TABLE = "goals"


class GoalRepository:
    @staticmethod
    def create(access_token: str, user_id: str, payload: dict) -> dict:
        client = supabase_as_user(access_token)
        row = {**payload, "user_id": user_id}
        res = client.table(TABLE).insert(row).execute()
        return res.data[0]
    @staticmethod
    def list_by_user(access_token: str, user_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
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

    @staticmethod
    def get_by_id(access_token: str, user_id: str, goal_id: str) -> dict | None:
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
    def update_priority_rank(access_token: str, user_id: str, goal_id: str, priority_rank: Optional[int]) -> dict | None:
        client = supabase_as_user(access_token)
        res = (
            client.table(TABLE)
            .update({"priority_rank": priority_rank})
            .eq("user_id", user_id)
            .eq("id", goal_id)
            .execute()
        )
        return res.data[0] if res.data else None