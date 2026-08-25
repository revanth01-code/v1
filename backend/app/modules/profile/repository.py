from typing import Optional
from app.core.supabase import supabase_as_user

TABLE = "financial_profile"


class ProfileRepository:
    """All Supabase queries for this module live here, and only here.
    Every query uses a client scoped to the requesting user's own JWT
    (via supabase_as_user), so Postgres RLS enforces the "only your own
    row" rule at the database level — even if a bug elsewhere in the app
    tried to query someone else's data, the database itself would refuse."""

    @staticmethod
    def get_by_user_id(access_token: str, user_id: str) -> Optional[dict]:
        client = supabase_as_user(access_token)
        res = client.table(TABLE).select("*").eq("user_id", user_id).maybe_single().execute()
        return res.data if res else None

    @staticmethod
    def create(access_token: str, user_id: str, payload: dict) -> dict:
        client = supabase_as_user(access_token)
        row = {**payload, "user_id": user_id}
        res = client.table(TABLE).insert(row).execute()
        return res.data[0]

    @staticmethod
    def update(access_token: str, user_id: str, payload: dict) -> dict:
        client = supabase_as_user(access_token)
        res = (
            client.table(TABLE)
            .update(payload)
            .eq("user_id", user_id)
            .execute()
        )
        return res.data[0]