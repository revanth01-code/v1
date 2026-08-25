from app.core.exceptions import AppError
from .repository import ProfileRepository
from .schemas import ProfileCreate, ProfileUpdate, ProfileOut


def _to_profile_out(row: dict) -> ProfileOut:
    income = row["monthly_income"]
    expenses = row["monthly_expenses"]
    return ProfileOut(
        **row,
        monthly_surplus=income - expenses,
    )


class ProfileService:
    @staticmethod
    def get_profile(access_token: str, user_id: str) -> ProfileOut:
        row = ProfileRepository.get_by_user_id(access_token, user_id)
        if not row:
            raise AppError("Profile not found — create one first", 404)
        return _to_profile_out(row)

    @staticmethod
    def create_profile(access_token: str, user_id: str, payload: ProfileCreate) -> ProfileOut:
        existing = ProfileRepository.get_by_user_id(access_token, user_id)
        if existing:
            raise AppError("Profile already exists — use update instead", 409)
        row = ProfileRepository.create(access_token, user_id, payload.model_dump())
        return _to_profile_out(row)

    @staticmethod
    def update_profile(access_token: str, user_id: str, payload: ProfileUpdate) -> ProfileOut:
        existing = ProfileRepository.get_by_user_id(access_token, user_id)
        if not existing:
            raise AppError("Profile not found — create one first", 404)

        # Only send fields that were actually provided, so unset fields
        # don't get overwritten with None in the database.
        updates = payload.model_dump(exclude_none=True)
        if not updates:
            return _to_profile_out(existing)

        row = ProfileRepository.update(access_token, user_id, updates)
        return _to_profile_out(row)