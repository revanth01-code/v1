# backend/app/modules/universe/repository.py
from app.core.supabase import supabase_admin

TABLE = "asset_universe"


class UniverseRepository:
    @staticmethod
    def list_assets(
        asset_class: str = None,
        subcategory: str = None,
        instrument_type: str = None,
        data_status: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[dict]:
        query = supabase_admin.table(TABLE).select("*")
        if asset_class:
            query = query.eq("asset_class", asset_class)
        if subcategory:
            query = query.eq("subcategory", subcategory)
        if instrument_type:
            query = query.eq("instrument_type", instrument_type)
        if data_status:
            query = query.eq("data_status", data_status)
            
        res = query.order("asset_name").range(offset, offset + limit - 1).execute()
        return res.data

    @staticmethod
    def get_by_identifier(identifier: str) -> dict | None:
        res = (
            supabase_admin.table(TABLE)
            .select("*")
            .eq("identifier", identifier)
            .maybe_single()
            .execute()
        )
        return res.data if res else None
