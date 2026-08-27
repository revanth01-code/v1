# backend/app/modules/universe/ingestion_service.py
from datetime import datetime, timezone
import logging
from app.core.supabase import supabase_admin
from .providers.amfi_provider import AMFIMutualFundProvider
from .repository import TABLE as UNIVERSE_TABLE

logger = logging.getLogger(__name__)


class UniverseIngestionService:
    @staticmethod
    def ingest_universe_discovery() -> int:
        """Discovers mutual funds from AMFI and caches their metadata.

        Bypasses bulk daily historical NAV updates to maintain speed.
        """
        provider = AMFIMutualFundProvider()
        try:
            assets = provider.fetch_assets()
        except Exception as e:
            logger.error(f"Discovery Ingestion skipped due to provider failure: {e}")
            # Keep cached data intact
            return 0

        if not assets:
            logger.warning("AMFI Provider returned zero schemes. Retaining existing cache.")
            return 0

        # Load existing cached prices to avoid overwriting them with NULLs on transient network issues
        try:
            existing_res = supabase_admin.table(UNIVERSE_TABLE).select("identifier, latest_price").execute()
            existing_prices = {row["identifier"]: row["latest_price"] for row in existing_res.data}
        except Exception as e:
            logger.warning(f"Could not query existing cached prices for preservation check: {e}")
            existing_prices = {}

        rows = []
        now_str = datetime.now(timezone.utc).isoformat()

        for asset in assets:
            price = asset.latest_price
            if price is None:
                # Retain previously cached price if available
                price = existing_prices.get(asset.identifier)

            # Freshness label matches presence of valid price/NAV
            freshness_status = "fresh" if price is not None else "unavailable"

            row = {
                "asset_name": asset.asset_name,
                "asset_class": asset.asset_class,
                "subcategory": asset.subcategory,
                "instrument_type": asset.instrument_type,
                "identifier": asset.identifier,
                "data_source": asset.data_source,
                "liquidity": asset.liquidity,
                "tax_classification": asset.tax_classification,
                "tax_rule_key": asset.tax_rule_key,
                "tax_metadata": asset.tax_metadata,
                "latest_price": price,
                "data_status": freshness_status,
                "last_fetched": now_str,
            }
            rows.append(row)

        chunk_size = 200
        upserted_count = 0

        for i in range(0, len(rows), chunk_size):
            chunk = rows[i : i + chunk_size]
            try:
                res = (
                    supabase_admin.table(UNIVERSE_TABLE)
                    .upsert(chunk, on_conflict="identifier")
                    .execute()
                )
                upserted_count += len(res.data)
            except Exception as e:
                logger.error(f"Failed to upsert chunk of assets into cache: {e}")
                continue

        logger.info(f"Ingested {upserted_count} schemes into asset_universe.")
        return upserted_count

    @staticmethod
    def check_data_freshness(last_fetched_iso: str) -> str:
        """Determines data_status code based on age in days."""
        if not last_fetched_iso:
            return "unavailable"
        try:
            dt = datetime.fromisoformat(last_fetched_iso.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - dt).days
            if age_days <= 1:
                return "fresh"
            elif age_days <= 3:
                return "recent"
            elif age_days <= 7:
                return "aging"
            else:
                return "stale"
        except Exception:
            return "unavailable"
