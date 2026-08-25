from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.constants import API_PREFIX
from app.core.exceptions import AppError
from app.middleware.error_handlers import app_error_handler, unhandled_error_handler
from app.middleware.logging import log_requests
from app.modules.auth.router import router as auth_router
from app.modules.profile.router import router as profile_router
from app.core.exceptions import AppError, FeasibilityBlockedError
from app.middleware.error_handlers import (
    app_error_handler,
    feasibility_blocked_handler,
    unhandled_error_handler,
)
from app.modules.goals.router import router as goals_router
from app.modules.emergency_fund.router import router as emergency_fund_router
from app.modules.retirement.router import router as retirement_router
from app.modules.funds.router import router as funds_router
from app.modules.chatbot.router import router as chatbot_router
from app.modules.dashboard.router import router as dashboard_router

def create_app() -> FastAPI:
    app = FastAPI(title="Goal-Based Investment Platform API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(log_requests)

    app.add_exception_handler(FeasibilityBlockedError, feasibility_blocked_handler)
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # Each future module adds one line here: app.include_router(<module>_router, prefix=API_PREFIX)
    app.include_router(auth_router, prefix=API_PREFIX)
    app.include_router(profile_router, prefix=API_PREFIX)
    app.include_router(goals_router, prefix=API_PREFIX)
    app.include_router(emergency_fund_router, prefix=API_PREFIX)
    app.include_router(retirement_router, prefix=API_PREFIX)
    app.include_router(funds_router, prefix=API_PREFIX)
    app.include_router(chatbot_router, prefix=API_PREFIX)
    app.include_router(dashboard_router, prefix=API_PREFIX)

    return app


app = create_app()