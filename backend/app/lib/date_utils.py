from datetime import date
from app.core.exceptions import AppError


def months_between(start_date: date, end_date: date) -> int:
    """Whole months between two dates, rounding down to the last date not yet
    reached (e.g. Jan 15 -> Mar 10 is 1 full month, not 2)."""
    if end_date <= start_date:
        raise AppError("target_date must be in the future", 422)

    months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
    if end_date.day < start_date.day:
        months -= 1
    return max(months, 0)

def add_years(base_date: date, years: int) -> date:
    """Adds whole years to a date, handling Feb 29 landing on a non-leap
    year by falling back to Feb 28."""
    try:
        return base_date.replace(year=base_date.year + years)
    except ValueError:
        return base_date.replace(month=2, day=28, year=base_date.year + years)