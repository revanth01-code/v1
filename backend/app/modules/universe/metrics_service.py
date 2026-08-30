# backend/app/modules/universe/metrics_service.py
"""Orchestration layer for Part 3C: Analytics & Metrics Engine.

Responsibilities:
  1. Discover which assets have sufficient historical observations.
  2. Run analytics.compute_metrics_for_asset() on each.
  3. Determine peer counts and reliability.
  4. Build the asset_metrics record and upsert it.
  5. Return a structured summary report for the caller.

Design decisions:
  - Assets with < MIN_OBS_DRAWDOWN (2) observations are SKIPPED entirely —
    there is nothing computable and storing an empty INSUFFICIENT record for
    1,808 assets would bloat the table without value.
  - Assets with >= 2 but < MIN_OBS_VOLATILITY (30) observations receive an
    INSUFFICIENT record so the data confidence is honestly recorded.
  - Assets with sufficient data receive full metric computation.
  - Peer groups are cached per (asset_class, subcategory) pair to avoid
    1809 individual COUNT queries.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from .analytics import (
    compute_metrics_for_asset,
    compute_data_confidence,
    compute_peer_reliability,
    MIN_OBS_DRAWDOWN,
    MIN_OBS_VOLATILITY,
)
from .metrics_repository import MetricsRepository, CALCULATION_VERSION

logger = logging.getLogger(__name__)

# Source tag stored in asset_metrics.source to identify origin of computation.
METRICS_SOURCE = "amfi_mfapi_historical"


class MetricsService:

    @staticmethod
    def compute_and_store_all(dry_run: bool = False) -> dict:
        """Compute and upsert metrics for every asset that has observations.

        Processing strategy:
          - Only assets present in asset_historical_observations are processed.
          - Assets with 0 observations are skipped without touching the DB.
          - Peer counts are resolved from asset_universe and cached in-memory.

        Args:
            dry_run: If True, compute metrics but do not write to DB. Useful
                     for validation and testing.

        Returns:
            A summary dict:
              {
                total_with_observations   : int,
                skipped_no_observations   : int (always 0 — we only process obs assets),
                computed_and_stored       : int,
                stored_insufficient       : int,
                store_failures            : int,
                asset_universe_total      : int,
                identifiers_processed     : list[str],
              }
        """
        summary = {
            "total_with_observations": 0,
            "computed_and_stored": 0,
            "stored_insufficient": 0,
            "store_failures": 0,
            "asset_universe_total": 0,
            "identifiers_processed": [],
        }

        # Step 1: Discover which identifiers have observations
        identifiers_with_obs = MetricsRepository.get_all_identifiers_with_observations()
        summary["total_with_observations"] = len(identifiers_with_obs)

        if not identifiers_with_obs:
            logger.info("No assets with historical observations found. Nothing to compute.")
            return summary

        logger.info(
            f"Computing metrics for {len(identifiers_with_obs)} identifiers "
            f"with historical observations."
        )

        # Step 2: In-memory peer count cache — avoid N×COUNT queries
        peer_cache: dict[tuple[str, str], int] = {}

        for identifier in identifiers_with_obs:
            try:
                result = MetricsService._process_one(
                    identifier=identifier,
                    peer_cache=peer_cache,
                    dry_run=dry_run,
                )
                if result == "stored":
                    summary["computed_and_stored"] += 1
                elif result == "insufficient":
                    summary["stored_insufficient"] += 1
                elif result == "failed":
                    summary["store_failures"] += 1
                # "skipped" means <2 obs — do not count in any stored bucket
                summary["identifiers_processed"].append(identifier)
            except Exception as e:
                logger.error(f"Unexpected error processing {identifier}: {e}")
                summary["store_failures"] += 1

        # Step 3: Compute and persist recommendation scores once for the entire universe
        if not dry_run:
            logger.info("Triggering recommendation score calculation for the universe...")
            try:
                scoring_summary = MetricsService.calculate_and_persist_recommendation_scores()
                summary["recommendation_scores_summary"] = scoring_summary
                logger.info(f"Recommendation scores computed successfully: {scoring_summary}")
            except Exception as e:
                logger.error(f"Failed to calculate and persist recommendation scores: {e}")
                summary["recommendation_scores_summary"] = {"error": str(e)}

        return summary

    @staticmethod
    def compute_and_store_one(identifier: str, dry_run: bool = False) -> dict:
        """Compute and upsert metrics for a single identifier.

        Returns a dict with keys:
            identifier, status, metrics (if computed), message
        """
        peer_cache: dict[tuple[str, str], int] = {}
        status = MetricsService._process_one(identifier, peer_cache, dry_run)
        stored = MetricsRepository.get_metrics_for_identifier(identifier)
        return {
            "identifier": identifier,
            "status": status,
            "record": stored,
        }

    @staticmethod
    def _process_one(
        identifier: str,
        peer_cache: dict[tuple[str, str], int],
        dry_run: bool,
    ) -> str:
        """Process a single identifier. Returns a status string:

          'stored'       — full metrics computed and upserted
          'insufficient' — not enough data; INSUFFICIENT record upserted
          'failed'       — computation succeeded but DB write failed
          'skipped'      — fewer than MIN_OBS_DRAWDOWN obs; nothing stored
        """
        # Fetch observations
        obs = MetricsRepository.get_observations_for_identifier(identifier)
        n = len(obs)

        if n < MIN_OBS_DRAWDOWN:
            # Nothing useful to compute or store.
            logger.debug(f"Skipping {identifier}: only {n} observation(s).")
            return "skipped"

        # Run analytics (pure, no DB)
        result = compute_metrics_for_asset(obs)

        # Resolve peer classification
        classification = MetricsRepository.get_asset_classification(identifier)
        asset_class = (classification or {}).get("asset_class", "unknown")
        subcategory = (classification or {}).get("subcategory", "unclassified")

        # Look up peer count (cached) — counts only assets with computed metrics
        # records, NOT all universe assets regardless of data availability.
        cache_key = (asset_class, subcategory)
        if cache_key not in peer_cache:
            peer_cache[cache_key] = MetricsRepository.count_peers_with_metrics(asset_class, subcategory)
        peer_count = peer_cache[cache_key]

        peer_reliability = compute_peer_reliability(peer_count)

        # Determine data confidence
        data_start = result.get("data_start_date")
        data_end = result.get("data_end_date")

        if data_start and data_end:
            confidence = compute_data_confidence(
                obs_count=n,
                data_start=date.fromisoformat(data_start),
                data_end=date.fromisoformat(data_end),
                peer_reliability=peer_reliability,
            )
        else:
            confidence = "INSUFFICIENT"

        # Build the record
        record = {
            "identifier": identifier,
            "metrics": result["metrics"],
            "source": METRICS_SOURCE,
            "calculation_version": CALCULATION_VERSION,
            "data_start_date": data_start,
            "data_end_date": data_end,
            "historical_observation_count": n,
            "peer_count": peer_count,
            "data_confidence": confidence,
            "peer_reliability": peer_reliability,
        }

        if dry_run:
            logger.info(
                f"[DRY RUN] {identifier}: confidence={confidence}, "
                f"peer_reliability={peer_reliability}, obs={n}"
            )
            return "stored" if result["sufficient_data"] else "insufficient"

        # Write to DB
        ok = MetricsRepository.upsert_metrics(record)
        if not ok:
            return "failed"

        if result["sufficient_data"]:
            logger.info(
                f"Stored metrics for {identifier}: "
                f"confidence={confidence}, peer_reliability={peer_reliability}, obs={n}"
            )
            return "stored"
        else:
            logger.info(
                f"Stored INSUFFICIENT metrics for {identifier}: obs={n}"
            )
            return "insufficient"

    @staticmethod
    def get_metrics_summary() -> dict:
        """Returns a high-level summary of what is currently in asset_metrics."""
        total = MetricsRepository.get_metrics_count()
        records = MetricsRepository.get_all_metrics(limit=500)

        confidence_counts: dict[str, int] = {}
        peer_reliability_counts: dict[str, int] = {}
        for rec in records:
            dc = rec.get("data_confidence", "UNKNOWN")
            pr = rec.get("peer_reliability", "UNKNOWN")
            confidence_counts[dc] = confidence_counts.get(dc, 0) + 1
            peer_reliability_counts[pr] = peer_reliability_counts.get(pr, 0) + 1

        return {
            "total_metrics_records": total,
            "by_data_confidence": confidence_counts,
            "by_peer_reliability": peer_reliability_counts,
        }

    @staticmethod
    def calculate_and_persist_recommendation_scores() -> dict:
        """Groups stored metrics by subcategory, calculates scores, and persists them.
        
        Does not recompute any historical observation analytics or perform provider fetches.
        """
        # Step 1: Retrieve all metrics records
        all_metrics_records = []
        page = 0
        page_size = 1000
        while True:
            batch = MetricsRepository.get_all_metrics(limit=page_size, offset=page * page_size)
            all_metrics_records.extend(batch)
            if len(batch) < page_size:
                break
            page += 1

        if not all_metrics_records:
            return {
                "total_processed": 0,
                "updated_scores": 0,
                "null_scores": 0,
                "failures": 0,
                "subcategories_processed": 0,
            }

        # Step 2: Build identifier -> subcategory mapping from asset_universe
        from app.modules.universe.repository import UniverseRepository
        id_to_subcat = {}
        page = 0
        page_size = 1000
        while True:
            assets = UniverseRepository.list_assets(limit=page_size, offset=page * page_size)
            for a in assets:
                id_to_subcat[a["identifier"]] = a["subcategory"]
            if len(assets) < page_size:
                break
            page += 1

        # Step 3: Group records by subcategory
        grouped_funds = {}
        for rec in all_metrics_records:
            identifier = rec["identifier"]
            subcat = id_to_subcat.get(identifier, "unknown")
            
            fund_data = {
                "identifier": identifier,
                "subcategory": subcat,
                "metrics": rec["metrics"],
                "data_confidence": rec["data_confidence"],
                "peer_reliability": rec["peer_reliability"],
            }
            if subcat not in grouped_funds:
                grouped_funds[subcat] = []
            grouped_funds[subcat].append(fund_data)

        # Step 4: Calculate and update scores per subcategory group
        summary = {
            "total_processed": 0,
            "updated_scores": 0,
            "null_scores": 0,
            "failures": 0,
            "subcategories_processed": len(grouped_funds),
        }
        
        from app.modules.universe.recommendation.scoring_engine import RecommendationScoringEngine
        for subcat, peer_funds in grouped_funds.items():
            scored_peers = RecommendationScoringEngine.calculate_scores(peer_funds)
            for f in scored_peers:
                identifier = f["identifier"]
                score = f.get("recommendation_score")
                
                success = MetricsRepository.update_recommendation_score(identifier, score)
                if success:
                    summary["total_processed"] += 1
                    if score is not None:
                        summary["updated_scores"] += 1
                    else:
                        summary["null_scores"] += 1
                else:
                    summary["failures"] += 1

        return summary
