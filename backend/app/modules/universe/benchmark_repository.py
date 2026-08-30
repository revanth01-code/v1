from __future__ import annotations
import logging
from app.core.supabase import supabase_admin

logger = logging.getLogger(__name__)

BENCHMARK_OBS_TABLE = "benchmark_historical_observations"
BENCHMARK_MAP_TABLE = "benchmark_mapping"


class BenchmarkRepository:
    @staticmethod
    def get_benchmark_for_subcategory(subcategory: str) -> str | None:
        try:
            res = (
                supabase_admin.table(BENCHMARK_MAP_TABLE)
                .select("index_name")
                .eq("subcategory", subcategory)
                .maybe_single()
                .execute()
            )
            return res.data["index_name"] if res and res.data else None
        except Exception as e:
            logger.error(f"Failed to fetch benchmark mapping for {subcategory}: {e}")
            return None

    @staticmethod
    def upsert_observations(index_name: str, rows: list[dict]) -> int:
        payload = [{"index_name": index_name, **r} for r in rows]
        count = 0
        chunk_size = 500
        for i in range(0, len(payload), chunk_size):
            chunk = payload[i:i + chunk_size]
            try:
                res = (
                    supabase_admin.table(BENCHMARK_OBS_TABLE)
                    .upsert(chunk, on_conflict="index_name,observation_date")
                    .execute()
                )
                count += len(res.data or [])
            except Exception as e:
                logger.error(f"Failed to upsert benchmark observations chunk for {index_name}: {e}")
        return count

    @staticmethod
    def get_observations(index_name: str) -> list[dict]:
        all_rows: list[dict] = []
        page = 0
        page_size = 1000
        while True:
            try:
                res = (
                    supabase_admin.table(BENCHMARK_OBS_TABLE)
                    .select("observation_date, close_value")
                    .eq("index_name", index_name)
                    .order("observation_date")
                    .range(page * page_size, (page + 1) * page_size - 1)
                    .execute()
                )
                batch = res.data or []
                all_rows.extend(batch)
                if len(batch) < page_size:
                    break
                page += 1
            except Exception as e:
                logger.error(f"Failed to fetch benchmark observations for {index_name}: {e}")
                break
        return all_rows