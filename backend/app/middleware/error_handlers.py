import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.exceptions import AppError, FeasibilityBlockedError

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Postgres / PostgREST error code classification
# ---------------------------------------------------------------------------
# PGRST3xx  — PostgREST-level JWT / auth errors
# 42501      — PostgreSQL insufficient_privilege (RLS policy violation)
# 235xx      — PostgreSQL integrity constraint violations (input errors)
# All others — remain unclassified and are treated as unexpected server errors
# ---------------------------------------------------------------------------
_PGRST_AUTH_CODES   = frozenset({"PGRST301", "PGRST302", "PGRST303"})
_PG_PERMISSION_CODE = "42501"
_PG_INPUT_CODES     = frozenset({"23502", "23503", "23505", "23514", "22001", "22003"})


async def postgrest_api_error_handler(request: Request, exc: Exception):
    """
    Global handler for ``postgrest.exceptions.APIError``.

    Maps well-known PostgREST/PostgreSQL error codes to clean HTTP responses.
    Unknown codes are intentionally left as 500 so that real programming bugs
    (wrong column name, missing table, bad data type, etc.) are never silently
    swallowed — they will still appear in server logs for diagnosis.
    """
    code    = getattr(exc, "code",    "") or ""
    message = getattr(exc, "message", "") or str(exc)
    details = getattr(exc, "details", None)

    if code in _PGRST_AUTH_CODES:
        # JWT validation failure — the caller's session has expired or the
        # token is invalid.  Return 401 so the frontend can re-authenticate.
        logger.warning(
            "postgrest_jwt_error",
            code=code,
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid or expired session. Please log in again."},
        )

    if code == _PG_PERMISSION_CODE:
        # Row-Level Security denied the operation.  The user is authenticated
        # but does not own the resource.
        logger.warning(
            "postgrest_rls_violation",
            code=code,
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=403,
            content={"error": "Permission denied."},
        )

    if code in _PG_INPUT_CODES:
        # Integrity constraint violation caused by bad caller input
        # (not-null, check, unique, foreign-key).  Safe to surface as 400.
        logger.warning(
            "postgrest_constraint_violation",
            code=code,
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid input: a database constraint was violated."},
        )

    # -----------------------------------------------------------------------
    # Unknown database error — do NOT silently map to 400/403.
    # Log full details for diagnosis and return a generic 500 to the client.
    # -----------------------------------------------------------------------
    logger.error(
        "postgrest_unexpected_error",
        code=code,
        # message and details are safe to log internally; they are NOT
        # forwarded to the frontend response body.
        db_message=message,
        db_details=details,
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(
        status_code=500,
        content={"error": "A database error occurred. Please try again later."},
    )


async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


async def feasibility_blocked_handler(request: Request, exc: FeasibilityBlockedError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "feasibility": exc.feasibility},
    )


async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("unhandled_server_error", error=str(exc))
    return JSONResponse(status_code=500, content={"error": "Internal server error"})