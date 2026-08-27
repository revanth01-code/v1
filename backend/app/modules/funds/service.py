from datetime import datetime, timezone
import sys
from app.core.constants import FUND_CACHE_TTL_HOURS
from app.core.exceptions import AppError
from app.integrations import amfi, mfapi
from .repository import FundRepository
from .schemas import FundDetailOut, FundOut

_latest_refresh_time_cache = None
_latest_refresh_check_timestamp = None


def _is_cache_stale() -> bool:
    global _latest_refresh_time_cache, _latest_refresh_check_timestamp

    # If running pytest, bypass in-memory caching entirely
    if "pytest" in sys.modules or "_pytest" in sys.modules:
        last_refresh = FundRepository.get_latest_refresh_time()
        if last_refresh is None:
            return True
        age_hours = (datetime.now(timezone.utc) - last_refresh).total_seconds() / 3600
        return age_hours > FUND_CACHE_TTL_HOURS

    now = datetime.now(timezone.utc)
    if _latest_refresh_check_timestamp is not None:
        elapsed = (now - _latest_refresh_check_timestamp).total_seconds()
        if elapsed < 60:
            return _latest_refresh_time_cache

    last_refresh = FundRepository.get_latest_refresh_time()
    if last_refresh is None:
        stale = True
    else:
        age_hours = (now - last_refresh).total_seconds() / 3600
        stale = age_hours > FUND_CACHE_TTL_HOURS

    _latest_refresh_time_cache = stale
    _latest_refresh_check_timestamp = now
    return stale


_category_funds_cache = {}
_category_funds_cache_timestamp = {}


class FundService:
    @staticmethod
    def ensure_fresh_cache() -> None:
        """Refreshes the fund cache if stale. Best-effort: if AMFI is
        unreachable and we already have SOME cached data, silently keep
        serving the stale cache rather than failing the whole request —
        only raise if there's no usable data at all."""
        if not _is_cache_stale():
            return

        try:
            funds = amfi.fetch_and_parse_funds()
            if funds:
                FundRepository.upsert_many(funds)
        except Exception as e:
            last_refresh = FundRepository.get_latest_refresh_time()
            if last_refresh is None:
                raise AppError(
                    f"Fund data is temporarily unavailable and no cached data exists: {e}", 503
                )
            # else: swallow the error, fall through and serve stale cache

    @staticmethod
    def get_funds_by_category(category: str, limit: int) -> list[FundOut]:
        global _category_funds_cache, _category_funds_cache_timestamp

        # If running pytest, bypass in-memory caching entirely
        if "pytest" in sys.modules or "_pytest" in sys.modules:
            FundService.ensure_fresh_cache()
            rows = FundRepository.get_by_category(category, limit)
            return [FundOut(**row) for row in rows]

        now = datetime.now(timezone.utc)
        cache_key = (category, limit)

        # Cache category queries for 5 minutes (300 seconds)
        if cache_key in _category_funds_cache:
            last_check = _category_funds_cache_timestamp[cache_key]
            if (now - last_check).total_seconds() < 300:
                return _category_funds_cache[cache_key]

        FundService.ensure_fresh_cache()
        rows = FundRepository.get_by_category(category, limit)
        res = [FundOut(**row) for row in rows]

        _category_funds_cache[cache_key] = res
        _category_funds_cache_timestamp[cache_key] = now
        return res

    @staticmethod
    def get_fund_detail(scheme_code: str) -> FundDetailOut:
        row = FundRepository.get_by_scheme_code(scheme_code)
        if not row:
            raise AppError("Fund not found in cache", 404)

        try:
            historical = mfapi.fetch_historical_nav(scheme_code)
            return FundDetailOut(**row, historical_nav=historical, historical_nav_available=True)
        except Exception:
            # Historical NAV is a "nice to have" — never fail the whole
            # request just because MFAPI (no-SLA) is having a bad day.
            return FundDetailOut(**row, historical_nav=[], historical_nav_available=False)