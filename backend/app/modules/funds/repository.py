# backend/app/modules/funds/repository.py
from datetime import datetime, timezone
import logging
from typing import Optional
from app.core.supabase import supabase_admin
from app.core.constants import LEGACY_TO_UNIVERSE_SUBCAT_MAP, UNIVERSE_TO_LEGACY_CAT_MAP

logger = logging.getLogger(__name__)

LEGACY_TABLE = "fund_cache"
UNIVERSE_TABLE = "asset_universe"


def format_nav_date(dt_str: Optional[str]) -> str:
    """Formats ISO datetime string to AMFI standard DD-Mmm-YYYY format."""
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%d-%b-%Y")
    except Exception:
        return ""


def resolve_legacy_category_from_row(row: dict) -> str:
    """Safely determines the legacy category for a fund.
    
    Returns 'unsupported' for any unknown or unmapped subcategory.
    """
    subcategory = row.get("subcategory", "")
    legacy_cat = UNIVERSE_TO_LEGACY_CAT_MAP.get(subcategory)
    if legacy_cat:
        return legacy_cat
    return "unsupported"


def to_legacy_dict(row: dict) -> dict:
    """Translates an asset_universe row format to legacy fund_cache structure."""
    subcategory = row.get("subcategory", "")
    legacy_cat = resolve_legacy_category_from_row(row)
    
    # We clean up UTC time formats to match legacy expectations
    last_updated_raw = row.get("last_updated") or row.get("last_fetched") or ""
    
    # Normalize category_raw value safely
    if subcategory in ["large_cap", "flexi_cap", "mid_cap", "small_cap"]:
        category_raw = f"Open Ended Schemes(Equity Scheme - {subcategory.replace('_', ' ').title()} Fund)"
    else:
        category_raw = f"Open Ended Schemes(Debt Scheme - {subcategory.replace('_', ' ').title()} Fund)"

    return {
        "scheme_code": row.get("identifier"),
        "scheme_name": row.get("asset_name"),
        "category": legacy_cat,
        "category_raw": category_raw,
        "latest_nav": float(row.get("latest_price")) if row.get("latest_price") is not None else 0.0,
        "nav_date": format_nav_date(last_updated_raw),
        "updated_at": last_updated_raw,
    }


class FundRepository:
    @staticmethod
    def _has_any_universe_mutual_funds() -> bool:
        """Determines if the asset_universe table has been populated with mutual funds."""
        try:
            res = (
                supabase_admin.table(UNIVERSE_TABLE)
                .select("id")
                .eq("instrument_type", "mutual_fund")
                .limit(1)
                .execute()
            )
            return bool(res.data and len(res.data) > 0)
        except Exception as e:
            logger.warning(f"Error checking mutual fund count in asset_universe: {e}")
            return False

    @staticmethod
    def get_latest_refresh_time() -> Optional[datetime]:
        """Tries reading latest refresh time from asset_universe, falls back to legacy fund_cache."""
        # 1. Try reading from asset_universe
        try:
            res = (
                supabase_admin.table(UNIVERSE_TABLE)
                .select("last_updated")
                .eq("instrument_type", "mutual_fund")
                .order("last_updated", desc=True)
                .limit(1)
                .execute()
            )
            if res.data and res.data[0]["last_updated"]:
                raw = res.data[0]["last_updated"]
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception as e:
            logger.warning(f"Failed to fetch refresh time from asset_universe: {e}")

        # 2. Fallback to legacy fund_cache
        try:
            res = (
                supabase_admin.table(LEGACY_TABLE)
                .select("updated_at")
                .order("updated_at", desc=True)
                .limit(1)
                .execute()
            )
            if res.data and res.data[0]["updated_at"]:
                raw = res.data[0]["updated_at"]
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception as e:
            logger.warning(f"Failed to fetch refresh time from legacy fund_cache fallback: {e}")

        return None

    @staticmethod
    def upsert_many(rows: list[dict]) -> None:
        """Preserves legacy write path: writes directly into legacy fund_cache."""
        chunk_size = 500
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i : i + chunk_size]
            try:
                supabase_admin.table(LEGACY_TABLE).upsert(chunk, on_conflict="scheme_code").execute()
            except Exception as e:
                logger.error(f"Failed to upsert to legacy fund_cache: {e}")

    @staticmethod
    def get_by_category(category: str, limit: int) -> list[dict]:
        """Tries reading from asset_universe primary source, falls back to fund_cache if empty."""
        subcategories = LEGACY_TO_UNIVERSE_SUBCAT_MAP.get(category, [])
        
        # 1. Try reading from asset_universe
        universe_success = False
        try:
            res = (
                supabase_admin.table(UNIVERSE_TABLE)
                .select("*")
                .eq("instrument_type", "mutual_fund")
                .in_("subcategory", subcategories)
                .order("asset_name")
                .limit(limit)
                .execute()
            )
            universe_success = True
            if res.data and len(res.data) > 0:
                return [to_legacy_dict(row) for row in res.data]
        except Exception as e:
            logger.warning(f"Failed to query mutual funds from asset_universe: {e}")

        # If query succeeded but returned 0 rows, check if universe has mutual funds.
        # If yes, return empty list (category has no active funds). Do not mix stale legacy data.
        if universe_success and FundRepository._has_any_universe_mutual_funds():
            logger.info(f"asset_universe has mutual funds, but category '{category}' is empty. Serving empty results.")
            return []

        # 2. Fallback to legacy fund_cache
        logger.info(f"Falling back to legacy fund_cache for category: {category}")
        try:
            res = (
                supabase_admin.table(LEGACY_TABLE)
                .select("*")
                .eq("category", category)
                .order("scheme_name")
                .limit(limit)
                .execute()
            )
            return res.data
        except Exception as e:
            logger.error(f"Fallback query to legacy fund_cache failed: {e}")
            return []

    @staticmethod
    def get_by_scheme_code(scheme_code: str) -> Optional[dict]:
        """Tries reading a single mutual fund from asset_universe, falls back to fund_cache."""
        # 1. Try reading from asset_universe
        universe_success = False
        try:
            res = (
                supabase_admin.table(UNIVERSE_TABLE)
                .select("*")
                .eq("instrument_type", "mutual_fund")
                .eq("identifier", scheme_code)
                .maybe_single()
                .execute()
            )
            universe_success = True
            if res and res.data:
                return to_legacy_dict(res.data)
        except Exception as e:
            logger.warning(f"Failed to query mutual fund {scheme_code} from asset_universe: {e}")

        if universe_success and FundRepository._has_any_universe_mutual_funds():
            logger.info(f"asset_universe is populated, but scheme_code '{scheme_code}' is missing. Returning None.")
            return None

        # 2. Fallback to legacy fund_cache
        logger.info(f"Falling back to legacy fund_cache for scheme_code: {scheme_code}")
        try:
            res = (
                supabase_admin.table(LEGACY_TABLE)
                .select("*")
                .eq("scheme_code", scheme_code)
                .maybe_single()
                .execute()
            )
            return res.data if res else None
        except Exception as e:
            logger.error(f"Fallback query to legacy fund_cache failed for scheme_code: {e}")
            return None