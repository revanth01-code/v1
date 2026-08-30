# backend/app/modules/universe/router.py
import os
from fastapi import APIRouter, Query, Depends, Header, HTTPException, status
from app.middleware.auth import get_current_user
from app.modules.auth.schemas import UserOut
from .schemas import AssetOut
from .service import UniverseService
from .ingestion_service import UniverseIngestionService
from .metrics_service import MetricsService
from .backfill_service import BackfillService, MAX_BATCH_LIMIT, DEFAULT_BATCH_LIMIT
from app.core.config import settings

router = APIRouter(prefix="/universe", tags=["universe"])

# Fetch the Admin key from environment variables
ADMIN_API_KEY = settings.ADMIN_API_KEY

import secrets


def verify_admin_key(x_admin_key: str = Header(None)):
    """FastAPI dependency to verify x-admin-key header against local environment configuration."""
    if not x_admin_key or not secrets.compare_digest(x_admin_key, ADMIN_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Invalid or missing x-admin-key header."
        )


@router.get("/assets", response_model=list[AssetOut])
def get_assets(
    asset_class: str = Query(None),
    subcategory: str = Query(None),
    instrument_type: str = Query(None),
    data_status: str = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """Retrieves all assets available in the investment universe, with optional

    filtering and offsets.
    """
    return UniverseService.get_all_assets(
        asset_class=asset_class,
        subcategory=subcategory,
        instrument_type=instrument_type,
        data_status=data_status,
        limit=limit,
        offset=offset
    )


@router.get("/assets/{identifier}", response_model=AssetOut)
def get_asset_detail(identifier: str):
    """Retrieves metadata and current pricing for a specific asset using its

    identifier.
    """
    return UniverseService.get_asset_detail(identifier)


@router.get("/recommendations", response_model=dict[str, list[AssetOut]])
def get_recommendations(risk_level: str = Query("mid")):
    """Returns normalized assets matching the target risk profile, structured

    by asset class.
    """
    return UniverseService.get_recommendations(risk_level)


@router.post("/refresh", status_code=status.HTTP_200_OK)
def trigger_universe_refresh(admin_key: None = Depends(verify_admin_key)):
    """Triggers dynamic AMFI mutual fund discovery ingestion.

    Protected: Only accessible via valid x-admin-key header verification.
    """
    from .ingestion_service import LockUnavailableError
    try:
        count = UniverseIngestionService.ingest_universe_discovery()
        return {
            "status": "success",
            "records_processed": count,
            "records_failed": 0  # Chunk failures are handled internally and logged
        }
    except LockUnavailableError:
        return {
            "status": "already_running"
        }


@router.post("/assets/{identifier}/refresh-history", status_code=status.HTTP_200_OK)
def trigger_asset_history_refresh(
    identifier: str,
    user: UserOut = Depends(get_current_user)
):
    """Refreshes daily historical observations cache for a single asset code.

    Protected: Requires a valid authenticated user session.
    """
    # Triggers synchronous update to let the user see the result immediately
    try:
        UniverseService.update_historical_cache(identifier)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Historical update failed: {e}"
        )
    return {
        "status": "success",
        "message": f"Successfully updated historical cache for asset {identifier}.",
        "identifier": identifier
    }


@router.post("/metrics/compute", status_code=status.HTTP_200_OK)
def trigger_metrics_computation(admin_key: None = Depends(verify_admin_key)):
    """Compute and store performance metrics for all assets with sufficient

    historical observations. Only assets present in asset_historical_observations
    are processed. Protected: requires x-admin-key header.
    """
    summary = MetricsService.compute_and_store_all(dry_run=False)
    return {
        "status": "success",
        "message": "Metrics computation complete.",
        "summary": summary,
    }


@router.post("/recommendations/compute", status_code=status.HTTP_200_OK)
def trigger_recommendation_scoring(admin_key: None = Depends(verify_admin_key)):
    """Groups stored metrics by subcategory, calculates scores, and updates the database.

    Protected: requires x-admin-key header.
    """
    summary = MetricsService.calculate_and_persist_recommendation_scores()
    return {
        "status": "success",
        "funds_scored": summary.get("updated_scores", 0),
        "funds_skipped": summary.get("null_scores", 0),
        "subcategories_processed": summary.get("subcategories_processed", 0)
    }


@router.post("/assets/{identifier}/compute-metrics", status_code=status.HTTP_200_OK)
def trigger_single_asset_metrics(
    identifier: str,
    admin_key: None = Depends(verify_admin_key)
):
    """Compute and store metrics for a single asset identifier.

    Protected: requires x-admin-key header.
    """
    result = MetricsService.compute_and_store_one(identifier, dry_run=False)
    return {
        "status": "success",
        "identifier": identifier,
        "computation_status": result["status"],
        "record": result["record"],
    }


@router.get("/metrics/summary", status_code=status.HTTP_200_OK)
def get_metrics_summary(user: UserOut = Depends(get_current_user)):
    """Returns a high-level summary of what is stored in asset_metrics.

    Protected: requires authenticated user session.
    """
    return MetricsService.get_metrics_summary()


@router.post("/history/backfill", status_code=status.HTTP_200_OK)
def trigger_history_backfill(
    limit: int = Query(DEFAULT_BATCH_LIMIT, ge=1, le=MAX_BATCH_LIMIT),
    subcategories: str = Query(
        None,
        description=(
            "Comma-separated subcategory names to target. "
            "Defaults to all recommendation-relevant categories."
        ),
    ),
    admin_key: None = Depends(verify_admin_key),
):
    """Batch-fetch MFAPI historical NAV data for recommendation-relevant

    mutual fund categories and compute metrics for each fetched asset.

    Assets that already have sufficient fresh observations (>= 252 obs,
    latest within 7 days) are automatically skipped.

    Processing is synchronous. Run multiple small batches to progressively
    expand historical coverage.

    Protected: requires x-admin-key header.

    Args:
        limit        : Max assets to process this call (1-{max_limit}, default {default}).
        subcategories: Comma-separated list of subcategory names.
                       Omit to target all 8 default recommendation categories.
    """.format(max_limit=MAX_BATCH_LIMIT, default=DEFAULT_BATCH_LIMIT)

    parsed_subcategories = None
    if subcategories:
        parsed_subcategories = [s.strip() for s in subcategories.split(",") if s.strip()]

    result = BackfillService.run_batch(
        limit=limit,
        subcategories=parsed_subcategories,
    )
    return result
