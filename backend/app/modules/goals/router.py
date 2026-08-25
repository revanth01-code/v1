from fastapi import APIRouter, Depends, status
from app.middleware.auth import get_current_user, get_access_token
from app.modules.auth.schemas import UserOut
from .schemas import GoalCheckResponse, GoalCreate, GoalOut
from .service import GoalService

router = APIRouter(prefix="/goals", tags=["goals"])


@router.post("/check", response_model=GoalCheckResponse)
def check_goal(payload: GoalCreate):
    # Deliberately no auth required here — this is a pure "what-if" preview,
    # nothing is read from or written to the database.
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
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    return GoalService.list_goals(token, user.id)


@router.get("/{goal_id}", response_model=GoalOut)
def get_goal(
    goal_id: str,
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    return GoalService.get_goal(token, user.id, goal_id)