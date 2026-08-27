# backend/app/modules/universe/backfill_service.py
"""Part 3D-A — Progressive Historical Data Expansion.

Orchestrates controlled batch ingestion of MFAPI historical NAV data for
recommendation-relevant mutual fund categories, followed by automatic
metrics computation for each successfully fetched asset.

Design decisions (see implementation_plan.md for full rationale):

  - Calls MFAPIHistoryProvider.fetch_history() directly rather than going
    through service.update_historical_cache(), because the latter carries
    threading/locking logic intended for user-facing lazy-loads, which is
    inappropriate here.  The provider call and DB upsert are identical.

  - Skip logic checks asset_historical_observations directly, NOT
    asset_universe.last_fetched, because last_fetched records AMFI metadata
    discovery time — not observation fetch time.

  - Pre-scan pass: builds a single in-memory map of
      identifier -> {count, latest_date}
    from asset_historical_observations before the main loop to avoid
    N per-asset count queries.

  - Metrics computation reuses MetricsService.compute_and_store_one()
    unchanged.  No analytics logic is duplicated here.

  - Processing is synchronous and single-threaded.  Callers control
    progress by running multiple small batches.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

from app.core.supabase import supabase_admin
from .providers.mfapi_provider import MFAPIHistoryProvider
from .metrics_service import MetricsService

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------

UNIVERSE_TABLE = "asset_universe"
OBS_TABLE = "asset_historical_observations"

# Subcategories targeted for progressive backfill (recommendation-relevant).
TARGET_SUBCATEGORIES: list[str] = [
    "large_cap",
    "flexi_cap",
    "mid_cap",
    "small_cap",
    "elss",
    "index_fund",
    "liquid",
    "short_duration",
]

# Skip an asset if it already has this many observations AND fresh data.
SUFFICIENT_OBS_COUNT: int = 252          # ~1 trading year of daily NAV

# "Fresh" = latest observation is within this many days of today.
FRESHNESS_THRESHOLD_DAYS: int = 7

# Maximum assets that can be processed in a single batch call.
MAX_BATCH_LIMIT: int = 50

# Default conservative batch size.
DEFAULT_BATCH_LIMIT: int = 10

# Chunk size for observation upserts (matches service.py convention).
UPSERT_CHUNK_SIZE: int = 300


# -----------------------------------------------------------------------
# Pure helper functions (unit-testable, no I/O)
# -----------------------------------------------------------------------

def _is_fresh_enough(count: int, latest_date: Optional[date]) -> bool:
    """Return True if an asset should be SKIPPED (has sufficient fresh obs).

    Skip conditions (both must hold):
      - count >= SUFFICIENT_OBS_COUNT
      - latest observation date is within FRESHNESS_THRESHOLD_DAYS of today
    """
    if count < SUFFICIENT_OBS_COUNT:
        return False
    if latest_date is None:
        return False
    days_old = (date.today() - latest_date).days
    return days_old <= FRESHNESS_THRESHOLD_DAYS


def _determine_candidates(
    obs_summary: dict[str, dict],
    assets: list[dict],
    limit: int,
) -> tuple[list[dict], int]:
    """Select up to `limit` candidate assets that need history fetched.

    Args:
        obs_summary : dict mapping identifier -> {"count": int, "latest": date | None}
        assets      : list of asset dicts from asset_universe (with identifier, asset_name, subcategory)
        limit       : maximum candidates to return

    Returns:
        (candidates, skipped_count)
          candidates   — list of asset dicts to process (len <= limit)
          skipped_count — number of assets skipped as already sufficient
    """
    candidates: list[dict] = []
    skipped = 0

    for asset in assets:
        ident = asset["identifier"]
        info = obs_summary.get(ident, {"count": 0, "latest": None})
        if _is_fresh_enough(info["count"], info["latest"]):
            skipped += 1
            continue
        candidates.append(asset)
        if len(candidates) >= limit:
            break

    return candidates, skipped


# -----------------------------------------------------------------------
# DB helpers (private — not exposed outside this module)
# -----------------------------------------------------------------------

def _build_obs_summary(target_identifiers: set[str]) -> dict[str, dict]:
    """Build a dict of identifier -> {count, latest} for the given set.

    Uses paginated reads from asset_historical_observations.
    Only considers identifiers in target_identifiers to avoid loading the
    entire table when it grows large.

    Returns:
        {
            "122639": {"count": 3258, "latest": date(2026, 8, 25)},
            ...
        }
    """
    summary: dict[str, dict] = {}

    # We iterate over a potentially large table, so paginate.
    # For the current DB state (one asset, 3258 rows) a single page suffices,
    # but this is written to scale correctly.
    page = 0
    page_size = 1000
    while True:
        try:
            res = (
                supabase_admin.table(OBS_TABLE)
                .select("identifier, observation_date")
                .range(page * page_size, (page + 1) * page_size - 1)
                .execute()
            )
            batch = res.data or []
            if not batch:
                break
            for row in batch:
                ident = row["identifier"]
                if ident not in target_identifiers:
                    continue
                try:
                    obs_date = date.fromisoformat(row["observation_date"])
                except (ValueError, TypeError):
                    continue
                if ident not in summary:
                    summary[ident] = {"count": 0, "latest": None}
                summary[ident]["count"] += 1
                cur_latest = summary[ident]["latest"]
                if cur_latest is None or obs_date > cur_latest:
                    summary[ident]["latest"] = obs_date
            if len(batch) < page_size:
                break
            page += 1
        except Exception as e:
            logger.error(f"Failed to build obs summary (page {page}): {e}")
            break

    return summary


def _fetch_assets_in_subcategories(subcategories: list[str]) -> list[dict]:
    """Fetch identifier, asset_name, subcategory for all assets in the given
    subcategories, ordered by identifier for deterministic resumable ordering.
    """
    assets: list[dict] = []
    for sub in subcategories:
        try:
            res = (
                supabase_admin.table(UNIVERSE_TABLE)
                .select("identifier, asset_name, subcategory")
                .eq("subcategory", sub)
                .order("identifier")
                .execute()
            )
            assets.extend(res.data or [])
        except Exception as e:
            logger.error(f"Failed to fetch assets for subcategory {sub}: {e}")
    return assets


def _upsert_observations(identifier: str, obs: list[dict]) -> int:
    """Upsert a list of observations for one identifier.

    obs items must have keys: observation_date, price_or_nav.
    Returns the number of rows submitted for upsert (not deduplicated count).
    """
    rows = [
        {
            "identifier": identifier,
            "observation_date": o["observation_date"],
            "price_or_nav": o["price_or_nav"],
        }
        for o in obs
    ]
    total = 0
    for i in range(0, len(rows), UPSERT_CHUNK_SIZE):
        chunk = rows[i: i + UPSERT_CHUNK_SIZE]
        try:
            supabase_admin.table(OBS_TABLE).upsert(
                chunk, on_conflict="identifier,observation_date"
            ).execute()
            total += len(chunk)
        except Exception as e:
            logger.error(f"Upsert chunk failed for {identifier} (offset {i}): {e}")
    return total


def _mark_universe_fetched(identifier: str) -> None:
    """Update asset_universe to mark that historical observations were fetched."""
    now_str = datetime.now(timezone.utc).isoformat()
    try:
        supabase_admin.table(UNIVERSE_TABLE).update({
            "data_status": "fresh",
            "last_fetched": now_str,
        }).eq("identifier", identifier).execute()
    except Exception as e:
        logger.warning(f"Could not update asset_universe.last_fetched for {identifier}: {e}")


# -----------------------------------------------------------------------
# Public service
# -----------------------------------------------------------------------

class BackfillService:

    @staticmethod
    def run_batch(
        limit: int = DEFAULT_BATCH_LIMIT,
        subcategories: Optional[list[str]] = None,
    ) -> dict:
        """Run one batch of historical data backfill.

        Args:
            limit         : Maximum number of assets to fetch in this call.
                            Clamped to [1, MAX_BATCH_LIMIT].
            subcategories : Subcategory names to target.
                            Defaults to all TARGET_SUBCATEGORIES.

        Returns a structured summary dict (see implementation_plan.md for schema).
        """
        limit = max(1, min(limit, MAX_BATCH_LIMIT))
        if not subcategories:
            subcategories = list(TARGET_SUBCATEGORIES)

        logger.info(f"Backfill batch started: limit={limit}, subcategories={subcategories}")

        # ── Step 1: Fetch candidate assets from universe ──────────────────────
        all_assets = _fetch_assets_in_subcategories(subcategories)
        total_eligible = len(all_assets)

        if not all_assets:
            logger.info("No assets found in target subcategories. Nothing to do.")
            return _empty_summary(limit, subcategories, 0)

        # ── Step 2: Pre-scan observations for skip logic ──────────────────────
        target_ids = {a["identifier"] for a in all_assets}
        obs_summary = _build_obs_summary(target_ids)

        # ── Step 3: Determine candidates (respects limit) ─────────────────────
        candidates, skipped_count = _determine_candidates(obs_summary, all_assets, limit)

        logger.info(
            f"Total eligible: {total_eligible}, "
            f"skipped (fresh): {skipped_count}, "
            f"this batch: {len(candidates)}"
        )

        # ── Step 4: Process each candidate ───────────────────────────────────
        results: list[dict] = []
        summary_counts = {
            "fetched_with_metrics": 0,
            "fetched_insufficient": 0,
            "fetched_metrics_failed": 0,
            "failed": 0,
            "total_observations_upserted": 0,
        }

        for asset in candidates:
            identifier = asset["identifier"]
            asset_name = asset["asset_name"]
            subcategory = asset["subcategory"]

            result_row: dict = {
                "identifier": identifier,
                "asset_name": asset_name,
                "subcategory": subcategory,
                "fetch_status": "failed",
                "observations_upserted": 0,
                "history_start": None,
                "history_end": None,
                "metrics_status": None,
            }

            try:
                # 4a. Fetch history from MFAPI (throttle is inside the provider)
                obs = MFAPIHistoryProvider.fetch_history(identifier)
                if not obs:
                    logger.warning(f"MFAPI returned no observations for {identifier}.")
                    summary_counts["failed"] += 1
                    results.append(result_row)
                    continue

                # 4b. Record date range before upsert
                obs_sorted = sorted(obs, key=lambda x: x["observation_date"])
                result_row["history_start"] = obs_sorted[0]["observation_date"]
                result_row["history_end"] = obs_sorted[-1]["observation_date"]

                # 4c. Upsert observations (idempotent)
                upserted = _upsert_observations(identifier, obs_sorted)
                result_row["observations_upserted"] = upserted
                summary_counts["total_observations_upserted"] += upserted

                # 4d. Update universe freshness marker
                _mark_universe_fetched(identifier)

                # 4e. Trigger metrics computation (reuses MetricsService exactly)
                try:
                    metrics_result = MetricsService.compute_and_store_one(identifier)
                    metrics_status = metrics_result.get("status", "unknown")
                except Exception as me:
                    logger.error(f"Metrics computation failed for {identifier}: {me}")
                    metrics_status = "error"

                result_row["metrics_status"] = metrics_status

                if metrics_status == "stored":
                    result_row["fetch_status"] = "fetched_with_metrics"
                    summary_counts["fetched_with_metrics"] += 1
                elif metrics_status in ("insufficient", "skipped"):
                    result_row["fetch_status"] = "fetched_insufficient"
                    summary_counts["fetched_insufficient"] += 1
                else:
                    result_row["fetch_status"] = "fetched_metrics_failed"
                    summary_counts["fetched_metrics_failed"] += 1

                logger.info(
                    f"Backfill complete for {identifier} ({asset_name}): "
                    f"obs={upserted}, metrics={metrics_status}"
                )

            except Exception as e:
                logger.error(f"Backfill failed for {identifier}: {e}")
                summary_counts["failed"] += 1

            results.append(result_row)

        return {
            "status": "success",
            "limit": limit,
            "subcategories_targeted": subcategories,
            "total_eligible_in_categories": total_eligible,
            "skipped_sufficient_fresh": skipped_count,
            "candidates_this_batch": len(candidates),
            "results": results,
            "summary": summary_counts,
        }


def _empty_summary(limit: int, subcategories: list[str], total: int) -> dict:
    return {
        "status": "success",
        "limit": limit,
        "subcategories_targeted": subcategories,
        "total_eligible_in_categories": total,
        "skipped_sufficient_fresh": 0,
        "candidates_this_batch": 0,
        "results": [],
        "summary": {
            "fetched_with_metrics": 0,
            "fetched_insufficient": 0,
            "fetched_metrics_failed": 0,
            "failed": 0,
            "total_observations_upserted": 0,
        },
    }
