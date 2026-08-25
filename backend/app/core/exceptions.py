from typing import Any

class AppError(Exception):
    """Raise this anywhere in a service/router — it turns into a clean
    JSON error response via the handler registered in main.py."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class FeasibilityBlockedError(AppError):
    """Raised when a goal can't be saved because it's infeasible. Carries
    the full feasibility breakdown so the frontend can show the user
    exactly what to adjust, instead of just a bare error string."""

    def __init__(self, message: str, feasibility: dict[str, Any]):
        super().__init__(message, status_code=422)
        self.feasibility = feasibility