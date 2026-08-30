from typing import Any
from fastapi import APIRouter, Depends, status
from app.middleware.auth import get_current_user, get_access_token
from app.modules.auth.schemas import UserOut
from .schemas import GoalCheckResponse, GoalCreate, GoalOut, GoalStrategyPreviewRequest, GoalStrategyPreviewResponse
from app.modules.universe.recommendation.schemas import GoalStrategyFinalizeRequest, GoalStrategyFinalizeResponse
from .service import GoalService
from .priority_schemas import PriorityRankIn, PriorityAnalysisOut
from .priority_service import PriorityService
from app.modules.goals.feasibility import (
    GoalFeasibilityPreviewRequest,
    GoalFeasibilityPreviewResponse,
    GoalFeasibilityApplyRequest,
    GoalFeasibilityApplyResponse,
    FeasibilityService
)

router = APIRouter(prefix="/goals", tags=["goals"])


@router.post("/check", response_model=GoalCheckResponse)
def check_goal(payload: GoalCreate):
    
    return GoalService.check(payload)


@router.post("", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreate,
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    return GoalService.create(token, user.id, payload)


@router.get("", response_model=list[GoalOut])
def list_goals(
    limit: int = 20,
    offset: int = 0,
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    return GoalService.list_goals(token, user.id, limit=limit, offset=offset)


@router.put("/priority", response_model=list[GoalOut])
def set_priority_ranks(
    payload: PriorityRankIn,
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    return PriorityService.set_priority_ranks(token, user.id, payload)


@router.get("/priority-analysis", response_model=PriorityAnalysisOut)
def get_priority_analysis(
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    return PriorityService.get_priority_analysis(token, user.id)


@router.post("/strategy/preview", response_model=GoalStrategyPreviewResponse)
def preview_goal_strategy(
    payload: GoalStrategyPreviewRequest,
    user: UserOut = Depends(get_current_user)
):
    """Generates an interactive strategy and tax preview for a goal, without persisting changes."""
    return GoalService.preview_strategy(payload)


@router.post("/strategy/finalize", response_model=GoalStrategyFinalizeResponse)
def finalize_goal_strategy(
    payload: GoalStrategyFinalizeRequest,
    user: UserOut = Depends(get_current_user)
):
    """Finalizes user preferences and tax optimization profile, returning a finalized strategy plan."""
    return GoalService.finalize_strategy(payload)


@router.post("/strategy/recommendations", response_model=Any)
def get_goal_recommendations_preview(
    payload: GoalStrategyFinalizeRequest,
    user: UserOut = Depends(get_current_user)
):
    """Generates ranked, compatible mutual fund recommendations based on final strategy and preferences."""
    return GoalService.get_recommendations_preview(payload)


@router.post("/feasibility/preview", response_model=GoalFeasibilityPreviewResponse)
def preview_goal_feasibility(
    payload: GoalFeasibilityPreviewRequest,
    user: UserOut = Depends(get_current_user)
):
    """Evaluates planned vs required investments and returns strategy alternatives."""
    return FeasibilityService.calculate_feasibility(payload)


@router.post("/feasibility/apply", response_model=GoalFeasibilityApplyResponse)
def apply_feasibility_alternative(
    payload: GoalFeasibilityApplyRequest,
    user: UserOut = Depends(get_current_user)
):
    """Applies a selected alternative strategy to generate a revised preview."""
    return FeasibilityService.apply_alternative(payload)


@router.get("/{goal_id}", response_model=GoalOut)
def get_goal(
    goal_id: str,
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    return GoalService.get_goal(token, user.id, goal_id)