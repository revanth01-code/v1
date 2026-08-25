from datetime import datetime, timezone
from app.core.supabase import supabase_admin

TABLE = "fund_cache"


class FundRepository:
    @staticmethod
    def get_latest_refresh_time() -> datetime | None:
        res = (
            supabase_admin.table(TABLE)
            .select("updated_at")
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        if not res.data:
            return None
        raw = res.data[0]["updated_at"]
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))

    @staticmethod
    def upsert_many(rows: list[dict]) -> None:
        # Chunk to keep individual payloads reasonable — AMFI's file has
        # tens of thousands of schemes before filtering.
        chunk_size = 500
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i : i + chunk_size]
            supabase_admin.table(TABLE).upsert(chunk, on_conflict="scheme_code").execute()

    @staticmethod
    def get_by_category(category: str, limit: int) -> list[dict]:
        res = (
            supabase_admin.table(TABLE)
            .select("*")
            .eq("category", category)
            .order("scheme_name")
            .limit(limit)
            .execute()
        )
        return res.data

    @staticmethod
    def get_by_scheme_code(scheme_code: str) -> dict | None:
        res = (
            supabase_admin.table(TABLE)
            .select("*")
            .eq("scheme_code", scheme_code)
            .maybe_single()
            .execute()
        )
        return res.data if res else None