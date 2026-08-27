from app.core.exceptions import AppError
from .repository import ProfileRepository
from .schemas import ProfileCreate, ProfileUpdate, ProfileOut


def _to_profile_out(row: dict, access_token: str = None) -> ProfileOut:
    income = row["monthly_income"]
    expenses = row["monthly_expenses"]
    
    essential = row.get("essential_expenses") or 0.0
    emi = row.get("emi_obligations") or 0.0
    mandatory = row.get("mandatory_commitments") or 0.0
    
    ef_contrib = 0.0
    if access_token:
        try:
            from app.modules.emergency_fund.repository import EmergencyFundRepository
            ef_plan = EmergencyFundRepository.get_by_user_id(access_token, row["user_id"])
            if ef_plan:
                ef_contrib = ef_plan.get("monthly_contribution") or 0.0
            else:
                ef_contrib = row.get("emergency_fund_contribution") or 0.0
        except Exception:
            ef_contrib = row.get("emergency_fund_contribution") or 0.0
    else:
        ef_contrib = row.get("emergency_fund_contribution") or 0.0

    available_capacity = max(income - essential - emi - mandatory - ef_contrib, 0.0)
    
    return ProfileOut(
        **row,
        monthly_surplus=income - expenses,
        available_capacity=available_capacity,
    )


class ProfileService:
    @staticmethod
    def get_profile(access_token: str, user_id: str) -> ProfileOut:
        row = ProfileRepository.get_by_user_id(access_token, user_id)
        if not row:
            raise AppError("Profile not found — create one first", 404)
        return _to_profile_out(row, access_token)

    @staticmethod
    def create_profile(access_token: str, user_id: str, payload: ProfileCreate) -> ProfileOut:
        existing = ProfileRepository.get_by_user_id(access_token, user_id)
        if existing:
            raise AppError("Profile already exists — use update instead", 409)
        row = ProfileRepository.create(access_token, user_id, payload.model_dump())
        return _to_profile_out(row, access_token)

    @staticmethod
    def update_profile(access_token: str, user_id: str, payload: ProfileUpdate) -> ProfileOut:
        existing = ProfileRepository.get_by_user_id(access_token, user_id)
        if not existing:
            raise AppError("Profile not found — create one first", 404)

        updates = payload.model_dump(exclude_none=True)
        if not updates:
            return _to_profile_out(existing, access_token)

        row = ProfileRepository.update(access_token, user_id, updates)
        return _to_profile_out(row, access_token)
