import structlog
import sentry_sdk

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.constants import API_PREFIX
from app.core.exceptions import AppError, FeasibilityBlockedError
from app.core.limiter import limiter

from app.middleware.error_handlers import (
    app_error_handler,
    feasibility_blocked_handler,
    postgrest_api_error_handler,
    unhandled_error_handler,
)
from app.middleware.logging import log_requests

from app.modules.auth.router import router as auth_router
from app.modules.chatbot.router import router as chatbot_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.emergency_fund.router import router as emergency_fund_router
from app.modules.funds.router import router as funds_router
from app.modules.goals.router import router as goals_router
from app.modules.notifications.router import router as notifications_router
from app.modules.portfolio.router import router as portfolio_router
from app.modules.profile.router import router as profile_router
from app.modules.recommendation.router import router as recommendation_router
from app.modules.retirement.router import router as retirement_router
from app.modules.simulation.router import router as simulation_router
from app.modules.universe.router import router as universe_router


if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.1,
        environment=settings.ENV,
    )


structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)


def create_app() -> FastAPI:
    app = FastAPI(title="Goal-Based Investment Platform API")

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=True,
    )

    # Request logging
    app.middleware("http")(log_requests)

    # Custom application errors
    app.add_exception_handler(
        FeasibilityBlockedError,
        feasibility_blocked_handler,
    )

    app.add_exception_handler(
        AppError,
        app_error_handler,
    )

    # PostgREST / Supabase database errors
    from postgrest.exceptions import APIError as PostgRESTAPIError

    app.add_exception_handler(
        PostgRESTAPIError,
        postgrest_api_error_handler,
    )

    # Generic fallback
    app.add_exception_handler(
        Exception,
        unhandled_error_handler,
    )

    # Health check
    @app.get("/health")
    def health():
        return {"status": "ok"}

    # API Routers
    app.include_router(auth_router, prefix=API_PREFIX)
    app.include_router(profile_router, prefix=API_PREFIX)
    app.include_router(goals_router, prefix=API_PREFIX)
    app.include_router(emergency_fund_router, prefix=API_PREFIX)
    app.include_router(retirement_router, prefix=API_PREFIX)
    app.include_router(funds_router, prefix=API_PREFIX)
    app.include_router(chatbot_router, prefix=API_PREFIX)
    app.include_router(dashboard_router, prefix=API_PREFIX)
    app.include_router(simulation_router, prefix=API_PREFIX)
    app.include_router(universe_router, prefix=API_PREFIX)
    app.include_router(portfolio_router, prefix=API_PREFIX)

    # Recommendation Engine
    app.include_router(recommendation_router, prefix=API_PREFIX)

    # Notifications
    app.include_router(notifications_router, prefix=API_PREFIX)

    return app


app = create_app()