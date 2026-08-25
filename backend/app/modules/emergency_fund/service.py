from app.core.exceptions import AppError
from app.modules.profile.repository import ProfileRepository
from .repository import EmergencyFundRepository
from .schemas import EmergencyFundCreate, EmergencyFundOut, EmergencyFundUpdate


def _get_monthly_expenses(access_token: str, user_id: str) -> float:
    profile = ProfileRepository.get_by_user_id(access_token, user_id)
    if not profile:
        raise AppError(
            "Set up your financial profile before creating an emergency fund plan.",
            422,
        )
    return profile["monthly_expenses"]


def _to_out(row: dict, monthly_expenses: float) -> EmergencyFundOut:
    target_amount = monthly_expenses * row["months_of_coverage"]
    remaining = max(target_amount - row["current_amount"], 0)

    time_to_target = None
    if row["monthly_contribution"] > 0:
        time_to_target = round(remaining / row["monthly_contribution"], 1)

    status = "complete" if row["current_amount"] >= target_amount else "building"

    return EmergencyFundOut(
        **row,
        monthly_expenses=monthly_expenses,
        target_amount=round(target_amount, 2),
        time_to_target_months=time_to_target,
        status=status,
    )


class EmergencyFundService:
    @staticmethod
    def get(access_token: str, user_id: str) -> EmergencyFundOut:
        row = EmergencyFundRepository.get_by_user_id(access_token, user_id)
        if not row:
            raise AppError("Emergency fund plan not found — create one first", 404)
        monthly_expenses = _get_monthly_expenses(access_token, user_id)
        return _to_out(row, monthly_expenses)

    @staticmethod
    def create(access_token: str, user_id: str, payload: EmergencyFundCreate) -> EmergencyFundOut:
        existing = EmergencyFundRepository.get_by_user_id(access_token, user_id)
        if existing:
            raise AppError("Emergency fund plan already exists — use update instead", 409)

        # Validates the profile exists before writing anything.
        monthly_expenses = _get_monthly_expenses(access_token, user_id)

        row = EmergencyFundRepository.create(access_token, user_id, payload.model_dump())
        return _to_out(row, monthly_expenses)

    @staticmethod
    def update(access_token: str, user_id: str, payload: EmergencyFundUpdate) -> EmergencyFundOut:
        existing = EmergencyFundRepository.get_by_user_id(access_token, user_id)
        if not existing:
            raise AppError("Emergency fund plan not found — create one first", 404)

        monthly_expenses = _get_monthly_expenses(access_token, user_id)

        updates = payload.model_dump(exclude_none=True)
        if not updates:
            return _to_out(existing, monthly_expenses)

        row = EmergencyFundRepository.update(access_token, user_id, updates)
        return _to_out(row, monthly_expenses)