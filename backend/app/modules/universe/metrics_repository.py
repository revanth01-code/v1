# backend/app/modules/universe/metrics_repository.py
"""Database access layer for asset metrics and historical observations.

Uses supabase_admin (service-role) for all operations — these are
server-side analytics writes, not user-facing mutations.

Follows the same pattern as repository.py in this module.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from app.core.supabase import supabase_admin

logger = logging.getLogger(__name__)

OBS_TABLE = "asset_historical_observations"
METRICS_TABLE = "asset_metrics"
UNIVERSE_TABLE = "asset_universe"

# Current version string stored in asset_metrics.calculation_version.
# Increment this when the calculation methodology changes so stale records
# can be identified and re-computed.
# v1.0 — initial implementation (full-series CAGR, peer count from universe)
# v1.1 — trailing-window 1y/3y/5y CAGR; peer_count from asset_metrics only
CALCULATION_VERSION = "1.1"


class MetricsRepository:
    # -----------------------------------------------------------------------
    # Historical Observations — read-only
    # -----------------------------------------------------------------------

    @staticmethod
    def get_observations_for_identifier(identifier: str) -> list[dict]:
        """Fetch ALL historical observations for one asset, sorted oldest-first.

        Uses pagination to bypass the PostgREST 1000-row default cap.
        Returns a list of dicts with keys: identifier, observation_date, price_or_nav.
        Returns an empty list on error.
        """
        all_rows: list[dict] = []
        page = 0
        page_size = 1000
        while True:
            try:
                res = (
                    supabase_admin.table(OBS_TABLE)
                    .select("identifier, observation_date, price_or_nav")
                    .eq("identifier", identifier)
                    .order("observation_date", desc=False)
                    .range(page * page_size, (page + 1) * page_size - 1)
                    .execute()
                )
                batch = res.data or []
                all_rows.extend(batch)
                if len(batch) < page_size:
                    break
                page += 1
            except Exception as e:
                logger.error(f"Failed to fetch observations for {identifier} (page {page}): {e}")
                break
        return all_rows


    @staticmethod
    def get_all_identifiers_with_observations() -> list[str]:
        """Returns the distinct set of identifiers that have at least one
        observation record. Uses pagination to handle large datasets.
        """
        identifiers: set[str] = set()
        page = 0
        page_size = 1000
        while True:
            try:
                res = (
                    supabase_admin.table(OBS_TABLE)
                    .select("identifier")
                    .range(page * page_size, (page + 1) * page_size - 1)
                    .execute()
                )
                batch = res.data or []
                if not batch:
                    break
                for row in batch:
                    identifiers.add(row["identifier"])
                if len(batch) < page_size:
                    break
                page += 1
            except Exception as e:
                logger.error(f"Failed to fetch identifiers with observations (page {page}): {e}")
                break
        return list(identifiers)

    @staticmethod
    def get_observation_count_by_identifier() -> dict[str, int]:
        """Returns a mapping of identifier -> observation count.

        Uses pagination to aggregate over the full table.
        """
        from collections import Counter
        counts: Counter = Counter()
        page = 0
        page_size = 1000
        while True:
            try:
                res = (
                    supabase_admin.table(OBS_TABLE)
                    .select("identifier")
                    .range(page * page_size, (page + 1) * page_size - 1)
                    .execute()
                )
                batch = res.data or []
                if not batch:
                    break
                for row in batch:
                    counts[row["identifier"]] += 1
                if len(batch) < page_size:
                    break
                page += 1
            except Exception as e:
                logger.error(f"Failed to count observations (page {page}): {e}")
                break
        return dict(counts)

    # -----------------------------------------------------------------------
    # Peer group — read from asset_universe
    # -----------------------------------------------------------------------

    @staticmethod
    def count_peers(asset_class: str, subcategory: str) -> int:
        """Count ALL assets in the same (asset_class, subcategory) in asset_universe.

        NOTE: This includes assets with no historical data. It is kept for
        internal reference only. Use count_peers_with_metrics() for peer_count
        stored in asset_metrics records.
        """
        try:
            res = (
                supabase_admin.table(UNIVERSE_TABLE)
                .select("identifier", count="exact")
                .eq("asset_class", asset_class)
                .eq("subcategory", subcategory)
                .execute()
            )
            return res.count or 0
        except Exception as e:
            logger.error(f"Failed to count universe peers for {asset_class}/{subcategory}: {e}")
            return 0

    @staticmethod
    def count_peers_with_metrics(asset_class: str, subcategory: str) -> int:
        """Count comparable assets in the same (asset_class, subcategory) that
        have a computed metrics record in asset_metrics.

        This is the correct peer_count to store — it represents the number of
        assets with usable performance data for comparison, not just any asset
        that appears in asset_universe regardless of data availability.

        Strategy (PostgREST does not support direct joins):
          1. Fetch all identifiers for this peer group from asset_universe.
          2. Check which of those identifiers exist in asset_metrics.
          3. Return the count of the intersection.
        """
        # Step 1: identifiers in this peer group from asset_universe
        try:
            universe_res = (
                supabase_admin.table(UNIVERSE_TABLE)
                .select("identifier")
                .eq("asset_class", asset_class)
                .eq("subcategory", subcategory)
                .execute()
            )
            peer_identifiers = [row["identifier"] for row in (universe_res.data or [])]
        except Exception as e:
            logger.error(
                f"Failed to fetch peer identifiers for {asset_class}/{subcategory}: {e}"
            )
            return 0

        if not peer_identifiers:
            return 0

        # Step 2: count how many of those have an asset_metrics record
        # Process in batches of 100 to stay within PostgREST in() filter limits
        count = 0
        batch_size = 100
        for i in range(0, len(peer_identifiers), batch_size):
            batch = peer_identifiers[i : i + batch_size]
            try:
                res = (
                    supabase_admin.table(METRICS_TABLE)
                    .select("identifier", count="exact")
                    .in_("identifier", batch)
                    .execute()
                )
                count += res.count or 0
            except Exception as e:
                logger.error(f"Failed to count metrics peers (batch starting {i}): {e}")
        return count

    @staticmethod
    def get_asset_classification(identifier: str) -> Optional[dict]:
        """Returns asset_class and subcategory for one identifier, or None."""
        try:
            res = (
                supabase_admin.table(UNIVERSE_TABLE)
                .select("identifier, asset_class, subcategory")
                .eq("identifier", identifier)
                .maybe_single()
                .execute()
            )
            return res.data if res else None
        except Exception as e:
            logger.error(f"Failed to fetch classification for {identifier}: {e}")
            return None

    # -----------------------------------------------------------------------
    # asset_metrics — upsert
    # -----------------------------------------------------------------------

    @staticmethod
    def upsert_metrics(record: dict) -> bool:
        """Upsert a single metrics record into asset_metrics.

        The unique constraint is on `identifier`. On conflict the full
        row is updated (including updated_at via the DB trigger).

        `record` must be a complete dict matching the asset_metrics columns:
            identifier, metrics, source, calculation_version,
            data_start_date, data_end_date, historical_observation_count,
            peer_count, data_confidence, peer_reliability

        Returns True on success, False on failure.
        """
        try:
            supabase_admin.table(METRICS_TABLE).upsert(
                record,
                on_conflict="identifier"
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to upsert metrics for {record.get('identifier', '?')}: {e}")
            return False

    @staticmethod
    def get_metrics_for_identifier(identifier: str) -> Optional[dict]:
        """Fetch the stored metrics record for one identifier, or None."""
        try:
            res = (
                supabase_admin.table(METRICS_TABLE)
                .select("*")
                .eq("identifier", identifier)
                .maybe_single()
                .execute()
            )
            return res.data if res else None
        except Exception as e:
            logger.error(f"Failed to fetch metrics for {identifier}: {e}")
            return None

    @staticmethod
    def get_all_metrics(limit: int = 500, offset: int = 0) -> list[dict]:
        """Fetch stored metrics records with optional pagination."""
        try:
            res = (
                supabase_admin.table(METRICS_TABLE)
                .select("*")
                .order("identifier")
                .range(offset, offset + limit - 1)
                .execute()
            )
            return res.data or []
        except Exception as e:
            logger.error(f"Failed to fetch all metrics: {e}")
            return []

    @staticmethod
    def get_metrics_count() -> int:
        """Returns the total number of records in asset_metrics."""
        try:
            res = (
                supabase_admin.table(METRICS_TABLE)
                .select("identifier", count="exact")
                .execute()
            )
            return res.count or 0
        except Exception as e:
            logger.error(f"Failed to count asset_metrics records: {e}")
            return 0

    @staticmethod
    def update_recommendation_score(identifier: str, score: Optional[float]) -> bool:
        """Update the recommendation_score column for a specific asset identifier.
        
        Returns True on success, False on failure.
        """
        try:
            supabase_admin.table(METRICS_TABLE).update(
                {"recommendation_score": score}
            ).eq("identifier", identifier).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to update recommendation_score for {identifier}: {e}")
            return False
