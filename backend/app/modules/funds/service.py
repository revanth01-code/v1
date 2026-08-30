from datetime import datetime, timezone
import logging
import sys

from app.core.constants import FUND_CACHE_TTL_HOURS
from app.core.exceptions import AppError
from app.integrations import mfapi

from .repository import FundRepository
from .schemas import FundDetailOut, FundOut


logger = logging.getLogger(__name__)

_latest_refresh_time_cache = None
_latest_refresh_check_timestamp = None

# Prevent repeated stale-check DB queries / refresh attempts in the same process.
_last_auto_refresh_attempt = None


def _is_cache_stale() -> bool:
    """
    Determines whether the mutual fund cache is stale.

    Priority:
    1. Last successful latest_nav sync from mf_sync_status.
    2. Existing asset_universe / legacy fund_cache refresh timestamp as fallback.
    """
    global _latest_refresh_time_cache, _latest_refresh_check_timestamp

    # If running pytest, bypass in-memory caching entirely.
    if "pytest" in sys.modules or "_pytest" in sys.modules:
        return _calculate_cache_staleness()

    now = datetime.now(timezone.utc)

    # Avoid repeated database freshness checks within 60 seconds.
    if _latest_refresh_check_timestamp is not None:
        elapsed = (now - _latest_refresh_check_timestamp).total_seconds()

        if elapsed < 60 and _latest_refresh_time_cache is not None:
            return _latest_refresh_time_cache

    stale = _calculate_cache_staleness()

    _latest_refresh_time_cache = stale
    _latest_refresh_check_timestamp = now

    return stale


def _calculate_cache_staleness() -> bool:
    """
    Calculates freshness using mf_sync_status first.

    Falls back to the latest refresh timestamp from asset_universe /
    legacy fund_cache for backward compatibility with already populated
    databases that do not yet have sync history.
    """
    now = datetime.now(timezone.utc)

    try:
        from app.modules.universe.sync_repository import SyncStatusRepository

        last_sync_time = SyncStatusRepository.get_last_successful_sync(
            "latest_nav"
        )

        if last_sync_time is not None:
            age_hours = (
                now - last_sync_time
            ).total_seconds() / 3600

            return age_hours > FUND_CACHE_TTL_HOURS

    except Exception as e:
        logger.warning(
            "Failed to read latest successful mutual fund sync: %s",
            e,
        )

    # Fallback for existing databases / legacy installations.
    last_refresh = FundRepository.get_latest_refresh_time()

    if last_refresh is None:
        return True

    age_hours = (
        now - last_refresh
    ).total_seconds() / 3600

    return age_hours > FUND_CACHE_TTL_HOURS


def _has_cached_fund_data() -> bool:
    """
    Returns True when fund data already exists in the database.

    Uses the existing repository refresh timestamp as the compatibility
    check for both asset_universe and legacy fund_cache.
    """
    return FundRepository.get_latest_refresh_time() is not None


_category_funds_cache = {}
_category_funds_cache_timestamp = {}


class FundService:
    @staticmethod
    def reset_refresh_throttle() -> None:
        """Resets the last auto refresh attempt timestamp, primarily for testing isolation."""
        global _last_auto_refresh_attempt
        _last_auto_refresh_attempt = None

    @staticmethod
    def ensure_fresh_cache() -> None:
        """
        Ensures mutual fund data exists and refreshes stale data safely.

        Behaviour:
        - Cold start:
            No cached data exists -> synchronous ingestion.
            If ingestion fails and no data exists -> controlled 503.

        - Fresh cache:
            Serve cached Supabase data immediately.

        - Stale cache:
            Attempt refresh using the existing distributed lock.
            If another instance is already refreshing, or refresh fails,
            continue serving existing stale data.

        Existing APIs and database architecture remain unchanged.
        """
        global _last_auto_refresh_attempt

        # ---------------------------------------------------------
        # 1. Cold start
        # ---------------------------------------------------------
        if not _has_cached_fund_data():
            logger.info(
                "No mutual fund data found. Starting cold-start ingestion."
            )

            try:
                from app.modules.universe.ingestion_service import (
                    UniverseIngestionService,
                )

                upserted_count = (
                    UniverseIngestionService.ingest_universe_discovery()
                )

                # Re-check database because another process may have
                # successfully populated the data.
                if upserted_count == 0 and not _has_cached_fund_data():
                    raise AppError(
                        "Fund data is temporarily unavailable and "
                        "no cached data exists.",
                        503,
                    )

            except Exception as e:
                # Race-condition protection:
                # another instance may have completed ingestion.
                if not _has_cached_fund_data():
                    logger.error(
                        "Cold-start mutual fund ingestion failed: %s",
                        e,
                    )

                    if isinstance(e, AppError):
                        raise

                    raise AppError(
                        "Fund data is temporarily unavailable and "
                        f"no cached data exists: {e}",
                        503,
                    )

            return

        # ---------------------------------------------------------
        # 2. Cached data exists and is still fresh
        # ---------------------------------------------------------
        if not _is_cache_stale():
            return

        # ---------------------------------------------------------
        # 3. Cached data exists but is stale
        # ---------------------------------------------------------
        now = datetime.now(timezone.utc)

        # Avoid repeatedly attempting refresh on every request if the
        # upstream provider is temporarily failing.
        if _last_auto_refresh_attempt is not None:
            elapsed = (
                now - _last_auto_refresh_attempt
            ).total_seconds()

            if elapsed < 60:
                logger.info(
                    "Mutual fund cache is stale, but a refresh attempt "
                    "was made recently. Serving cached data."
                )
                return

        _last_auto_refresh_attempt = now

        try:
            from app.modules.universe.ingestion_service import (
                UniverseIngestionService,
                LockUnavailableError,
            )

            logger.info(
                "Mutual fund cache is stale. "
                "Triggering automatic AMFI refresh."
            )

            UniverseIngestionService.ingest_universe_discovery()

            # Clear freshness cache so the next request reads the
            # latest sync state.
            global _latest_refresh_time_cache
            global _latest_refresh_check_timestamp

            _latest_refresh_time_cache = None
            _latest_refresh_check_timestamp = None

        except LockUnavailableError:
            logger.info(
                "Mutual fund refresh is already running on another "
                "instance. Serving cached stale data."
            )

        except Exception as e:
            logger.warning(
                "Automatic mutual fund refresh failed: %s. "
                "Serving existing cached data.",
                e,
            )

    @staticmethod
    def get_funds_by_category(
        category: str,
        limit: int,
    ) -> list[FundOut]:
        global _category_funds_cache
        global _category_funds_cache_timestamp

        # Pytest: bypass in-memory category cache entirely.
        if "pytest" in sys.modules or "_pytest" in sys.modules:
            FundService.ensure_fresh_cache()

            rows = FundRepository.get_by_category(
                category,
                limit,
            )

            return [
                FundOut(**row)
                for row in rows
            ]

        now = datetime.now(timezone.utc)
        cache_key = (category, limit)

        # ---------------------------------------------------------
        # Category response cache: 5 minutes
        # ---------------------------------------------------------
        if cache_key in _category_funds_cache:
            last_check = _category_funds_cache_timestamp[cache_key]

            if (
                now - last_check
            ).total_seconds() < 300:
                return _category_funds_cache[cache_key]

        # Ensure database cache is available/fresh.
        FundService.ensure_fresh_cache()

        rows = FundRepository.get_by_category(
            category,
            limit,
        )

        result = [
            FundOut(**row)
            for row in rows
        ]

        _category_funds_cache[cache_key] = result
        _category_funds_cache_timestamp[cache_key] = now

        return result

    @staticmethod
    def get_fund_detail(
        scheme_code: str,
    ) -> FundDetailOut:
        row = FundRepository.get_by_scheme_code(
            scheme_code
        )

        if not row:
            raise AppError(
                "Fund not found in cache",
                404,
            )

        try:
            historical = mfapi.fetch_historical_nav(
                scheme_code
            )

            return FundDetailOut(
                **row,
                historical_nav=historical,
                historical_nav_available=True,
            )

        except Exception:
            # Historical NAV is optional.
            # A temporary MFAPI failure should never fail
            # the entire fund detail request.
            return FundDetailOut(
                **row,
                historical_nav=[],
                historical_nav_available=False,
            )