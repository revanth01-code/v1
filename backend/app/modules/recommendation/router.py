# backend/app/modules/recommendation/router.py
from fastapi import APIRouter, Depends
from app.middleware.auth import get_current_user
from app.modules.auth.schemas import UserOut
from .models import RecommendationRequest, RecommendationResponse
from .orchestrator import RecommendationOrchestrator

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

@router.post("/preview")
def get_recommendation_preview(
    payload: RecommendationRequest,
    user: UserOut = Depends(get_current_user)
):
    """Unified entrypoint coordinating goal feasibility, asset category allocation, tax options, and deterministic fund recommendations."""
    return RecommendationOrchestrator.get_recommendation_preview(payload)
