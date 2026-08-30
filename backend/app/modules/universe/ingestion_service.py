# backend/app/modules/universe/ingestion_service.py
from datetime import datetime, timezone
import logging
import time
from app.core.supabase import supabase_admin
from .providers.amfi_provider import AMFIMutualFundProvider
from .repository import TABLE as UNIVERSE_TABLE
from .sync_repository import SyncStatusRepository

logger = logging.getLogger(__name__)


class LockUnavailableError(Exception):
    """Raised when the PostgreSQL Advisory Lock is already held by another process."""
    pass


class UniverseIngestionService:
    @staticmethod
    def ingest_universe_discovery() -> int:
        """Discovers mutual funds from AMFI and caches their metadata.

        Bypasses bulk daily historical NAV updates to maintain speed.
        """
        start_time = time.time()
        
        # 1. Acquire transaction lock and start sync log in database
        sync_id = None
        try:
            sync_id = SyncStatusRepository.try_start_sync("latest_nav")
            if not sync_id:
                logger.info("Ingestion lock is already held. Ingestion skipped (already running).")
                raise LockUnavailableError("Distributed sync lock is already held.")
        except LockUnavailableError:
            raise
        except Exception as e:
            # Fallback: logging/locking database failure must not halt standard ingestion flow
            logger.warning(f"Failed to acquire advisory lock due to database error: {e}")
            
        try:
            provider = AMFIMutualFundProvider()
            
            # We track assets fetch separately because its failure is caught and returns 0 (original behavior)
            try:
                assets = provider.fetch_assets()
            except Exception as provider_err:
                logger.error(f"Discovery Ingestion skipped due to provider failure: {provider_err}")
                
                # Record failed sync in database
                duration = time.time() - start_time
                if sync_id:
                    try:
                        SyncStatusRepository.complete_sync_failure(
                            sync_id, error_message=str(provider_err)[:500], duration_seconds=duration
                        )
                    except Exception as log_err:
                        logger.warning(f"Failed to record sync failure in database: {log_err}")
                
                return 0  # Original behavior: return 0 on provider fetch failure

            if not assets:
                logger.warning("AMFI Provider returned zero schemes. Retaining existing cache.")
                duration = time.time() - start_time
                if sync_id:
                    try:
                        SyncStatusRepository.complete_sync_success(
                            sync_id, records_processed=0, records_failed=0, duration_seconds=duration
                        )
                    except Exception as e:
                        logger.warning(f"Failed to record sync success in database: {e}")
                return 0

            # Execute database queries & upserts
            # If these throw unexpected exceptions (which originally propagated), we catch, record sync failure, and re-raise.
            try:
                # Load existing cached prices to avoid overwriting them with NULLs on transient network issues
                try:
                    existing_res = supabase_admin.table(UNIVERSE_TABLE).select("identifier, latest_price").execute()
                    existing_prices = {row["identifier"]: row["latest_price"] for row in existing_res.data}
                except Exception as e:
                    logger.warning(f"Could not query existing cached prices for preservation check: {e}")
                    existing_prices = {}

                rows = []
                now_str = datetime.now(timezone.utc).isoformat()
                records_failed = 0

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
                        records_failed += len(chunk)
                        continue

                logger.info(f"Ingested {upserted_count} schemes into asset_universe.")
                
                # Record successful sync
                duration = time.time() - start_time
                if sync_id:
                    try:
                        SyncStatusRepository.complete_sync_success(
                            sync_id, 
                            records_processed=upserted_count, 
                            records_failed=records_failed, 
                            duration_seconds=duration
                        )
                    except Exception as e:
                        logger.warning(f"Failed to record sync success in database: {e}")
                        
                return upserted_count

            except Exception as ingest_err:
                # Record failed sync in database
                duration = time.time() - start_time
                if sync_id:
                    try:
                        SyncStatusRepository.complete_sync_failure(
                            sync_id, error_message=str(ingest_err)[:500], duration_seconds=duration
                        )
                    except Exception as log_err:
                        logger.warning(f"Failed to record sync failure in database: {log_err}")
                
                # Re-raise the original exception
                raise ingest_err
        finally:
            pass

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
