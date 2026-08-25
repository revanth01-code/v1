from datetime import date
from app.core.exceptions import AppError
from app.lib.date_utils import add_years
from app.lib.finance_math import calculate_growing_annuity_pv
from app.modules.feasibility_engine.schemas import FeasibilityInput
from app.modules.feasibility_engine.service import FeasibilityEngine
from app.modules.profile.repository import ProfileRepository
from .repository import RetirementRepository
from .schemas import RetirementCreate, RetirementOut, RetirementUpdate


def _get_monthly_expenses(access_token: str, user_id: str) -> float:
    profile = ProfileRepository.get_by_user_id(access_token, user_id)
    if not profile:
        raise AppError(
            "Set up your financial profile before creating a retirement plan.", 422
        )
    return profile["monthly_expenses"]


def _to_out(row: dict, current_monthly_expense: float) -> RetirementOut:
    years_to_retirement = row["retirement_age"] - row["current_age"]
    years_in_retirement = row["life_expectancy"] - row["retirement_age"]

    # Step 1: inflate today's annual expense forward to the retirement date
    annual_expense_today = current_monthly_expense * 12
    annual_expense_at_retirement = annual_expense_today * (
        (1 + row["inflation_pct"] / 100) ** years_to_retirement
    )

    # Step 2: required corpus = present value (as of retirement date) of a
    # growing annuity that pays annual_expense_at_retirement, growing with
    # inflation each year, for the whole retirement period.
    required_corpus = calculate_growing_annuity_pv(
        first_payment=annual_expense_at_retirement,
        periods=years_in_retirement,
        rate_pct=row["post_retirement_return_pct"],
        growth_pct=row["inflation_pct"],
    )

    # Step 3: check feasibility of reaching required_corpus by the
    # retirement date, given existing corpus + planned SIP. inflation_pct=0
    # here deliberately — required_corpus is already expressed in
    # retirement-date rupees, so the engine shouldn't inflate it again.
    retirement_date = add_years(date.today(), years_to_retirement)
    feasibility_input = FeasibilityInput(
        target_amount=required_corpus,
        target_date=retirement_date,
        monthly_contribution=row["planned_monthly_contribution"],
        lumpsum_amount=row["existing_retirement_corpus"],
        expected_return_pct=row["pre_retirement_return_pct"],
        inflation_pct=0,
    )
    feasibility = FeasibilityEngine.check(feasibility_input)

    return RetirementOut(
        **row,
        current_monthly_expense=current_monthly_expense,
        years_to_retirement=years_to_retirement,
        years_in_retirement=years_in_retirement,
        required_corpus=round(required_corpus, 2),
        feasibility_status=feasibility.status,
        feasibility_details=feasibility.model_dump(),
    )


class RetirementService:
    @staticmethod
    def get(access_token: str, user_id: str) -> RetirementOut:
        row = RetirementRepository.get_by_user_id(access_token, user_id)
        if not row:
            raise AppError("Retirement plan not found — create one first", 404)
        expenses = _get_monthly_expenses(access_token, user_id)
        return _to_out(row, expenses)

    @staticmethod
    def create(access_token: str, user_id: str, payload: RetirementCreate) -> RetirementOut:
        existing = RetirementRepository.get_by_user_id(access_token, user_id)
        if existing:
            raise AppError("Retirement plan already exists — use update instead", 409)

        expenses = _get_monthly_expenses(access_token, user_id)
        row = RetirementRepository.create(access_token, user_id, payload.model_dump())
        # Note: unlike goals, we deliberately do NOT block on infeasible here —
        # retirement planning is iterative by nature, per product decision.
        return _to_out(row, expenses)

    @staticmethod
    def update(access_token: str, user_id: str, payload: RetirementUpdate) -> RetirementOut:
        existing = RetirementRepository.get_by_user_id(access_token, user_id)
        if not existing:
            raise AppError("Retirement plan not found — create one first", 404)

        expenses = _get_monthly_expenses(access_token, user_id)
        updates = payload.model_dump(exclude_none=True)
        if not updates:
            return _to_out(existing, expenses)

        merged = {**existing, **updates}
        if merged["retirement_age"] <= merged["current_age"]:
            raise AppError("retirement_age must be greater than current_age", 422)
        if merged["life_expectancy"] <= merged["retirement_age"]:
            raise AppError("life_expectancy must be greater than retirement_age", 422)

        row = RetirementRepository.update(access_token, user_id, updates)
        return _to_out(row, expenses)