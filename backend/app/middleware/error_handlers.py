from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.exceptions import AppError, FeasibilityBlockedError


async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


async def unhandled_error_handler(request: Request, exc: Exception):
    print(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"error": "Internal server error"})

async def feasibility_blocked_handler(request: Request, exc: FeasibilityBlockedError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "feasibility": exc.feasibility},
    )