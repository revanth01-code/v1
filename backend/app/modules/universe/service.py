# backend/app/modules/universe/service.py
from datetime import datetime, timezone
import logging
import threading
from app.core.exceptions import AppError
from app.core.supabase import supabase_admin
from .providers.mfapi_provider import MFAPIHistoryProvider
from .repository import UniverseRepository
from .schemas import AssetOut

logger = logging.getLogger(__name__)

# Concurrency locking for single-asset historical updates
history_locks = {}
lock_mutex = threading.Lock()


class UniverseService:
    @staticmethod
    def get_all_assets(
        asset_class: str = None,
        subcategory: str = None,
        instrument_type: str = None,
        data_status: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[AssetOut]:
        rows = UniverseRepository.list_assets(
            asset_class, subcategory, instrument_type, data_status, limit, offset
        )
        return [AssetOut(**row) for row in rows]

    @staticmethod
    def update_historical_cache(scheme_code: str) -> None:
        """Fetches and updates historical cache for a single scheme with locking."""
        # 1. Thread lock check to prevent concurrent duplicate fetching
        with lock_mutex:
            if scheme_code in history_locks:
                logger.info(f"Historical refresh already active for {scheme_code}. Skipping duplicate thread.")
                return
            history_locks[scheme_code] = True

        try:
            logger.info(f"Fetching historical observations from provider for {scheme_code}...")
            obs = MFAPIHistoryProvider.fetch_history(scheme_code)
            if not obs:
                logger.warning(f"Provider returned no observations for {scheme_code}.")
                return

            rows = []
            for o in obs:
                rows.append({
                    "identifier": scheme_code,
                    "observation_date": o["observation_date"],
                    "price_or_nav": o["price_or_nav"]
                })

            # Upsert observations cache in chunks
            chunk_size = 300
            for i in range(0, len(rows), chunk_size):
                chunk = rows[i : i + chunk_size]
                supabase_admin.table("asset_historical_observations").upsert(
                    chunk, on_conflict="identifier,observation_date"
                ).execute()

            # Update last_fetched time and status of parent asset
            now_str = datetime.now(timezone.utc).isoformat()
            supabase_admin.table("asset_universe").update({
                "last_fetched": now_str,
                "data_status": "fresh"
            }).eq("identifier", scheme_code).execute()
            logger.info(f"Successfully refreshed and cached observations for {scheme_code}.")

        except Exception as e:
            logger.error(f"Error during historical refresh loop for {scheme_code}: {e}")
        finally:
            with lock_mutex:
                history_locks.pop(scheme_code, None)

    @staticmethod
    def ensure_historical_cache(scheme_code: str) -> None:
        """Checks cache age and ensures observations exist.

        Implements lazy loading background thread updates to protect UX.
        """
        asset = UniverseRepository.get_by_identifier(scheme_code)
        if not asset:
            return

        last_fetched_str = asset.get("last_fetched")
        is_stale = True
        if last_fetched_str:
            try:
                dt = datetime.fromisoformat(last_fetched_str.replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - dt).days
                if age_days < 7:
                    is_stale = False
            except Exception:
                pass

        # Check if observations cache has records
        try:
            obs_check = (
                supabase_admin.table("asset_historical_observations")
                .select("id")
                .eq("identifier", scheme_code)
                .limit(1)
                .execute()
            )
            has_obs = len(obs_check.data) > 0
        except Exception as e:
            logger.error(f"Failed to check historical obs count: {e}")
            has_obs = False

        if not is_stale and has_obs:
            return

        # Case A: Stale but history exists -> Return immediately, refresh in background thread
        if is_stale and has_obs:
            logger.info(f"Observations stale for {scheme_code} but exist. Initiating background refresh.")
            bg_thread = threading.Thread(
                target=UniverseService.update_historical_cache,
                args=(scheme_code,),
                daemon=True
            )
            bg_thread.start()
            return

        # Case B: No cache exists -> Fetch synchronously to show data on details load
        if not has_obs:
            logger.info(f"No observations cached for {scheme_code}. Fetching synchronously.")
            UniverseService.update_historical_cache(scheme_code)

    @staticmethod
    def get_asset_detail(identifier: str) -> AssetOut:
        # Check and guarantee historical observations progressively
        try:
            UniverseService.ensure_historical_cache(identifier)
        except Exception as e:
            logger.warning(f"Error checking cache validation for {identifier}: {e}")

        row = UniverseRepository.get_by_identifier(identifier)
        if not row:
            raise AppError("Asset not found in universe", 404)
        return AssetOut(**row)

    @staticmethod
    def get_recommendations(risk_level: str) -> dict[str, list[AssetOut]]:
        # Retrieve all assets in the universe
        all_assets = UniverseRepository.list_assets(limit=300)
        
        # Filter and structure them by asset class
        equity_assets = [AssetOut(**a) for a in all_assets if a["asset_class"] == "equity"]
        debt_assets = [AssetOut(**a) for a in all_assets if a["asset_class"] == "debt"]
        div_assets = [AssetOut(**a) for a in all_assets if a["asset_class"] == "diversifier"]
        
        # Select target recommendations based on risk level
        if risk_level == "low":
            recommended_equity = [a for a in equity_assets if a.subcategory in ("large_cap", "index_fund")]
            recommended_debt = [a for a in debt_assets if a.subcategory in ("liquid", "overnight", "short_duration")]
            recommended_div = []
        elif risk_level == "high":
            recommended_equity = [a for a in equity_assets if a.subcategory in ("flexi_cap", "mid_cap", "small_cap", "etf")]
            recommended_debt = [a for a in debt_assets if a.subcategory in ("liquid")]
            recommended_div = [a for a in div_assets if a.subcategory in ("gold_etf", "reit")]
        else:  # moderate / mid
            recommended_equity = [a for a in equity_assets if a.subcategory in ("large_cap", "flexi_cap", "index_fund")]
            recommended_debt = [a for a in debt_assets if a.subcategory in ("liquid", "money_market")]
            recommended_div = [a for a in div_assets if a.subcategory in ("gold_fund")]
            
        return {
            "equity": recommended_equity[:3],
            "debt": recommended_debt[:3],
            "diversifier": recommended_div[:2]
        }
