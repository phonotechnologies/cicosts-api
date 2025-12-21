"""
CICosts API - FastAPI Application

Main entry point for the API.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sentry_sdk

from slowapi.errors import RateLimitExceeded

from app.config import settings as app_settings

# Initialize Sentry for error tracking (prod/staging only)
if app_settings.ENVIRONMENT in ("prod", "staging"):
    sentry_sdk.init(
        dsn="https://67302d193483c4c29fbc32428975b422@o4510575255945216.ingest.us.sentry.io/4510575259811840",
        environment=app_settings.ENVIRONMENT,
        send_default_pii=True,
        traces_sample_rate=0.1,  # 10% of requests for performance monitoring
    )
from app.routers import health, auth, webhooks, dashboard, alerts, settings, billing, limits
from app.middleware.rate_limit import (
    RateLimitMiddleware,
    limiter,
    rate_limit_exceeded_handler,
)
from app.services.logging_service import (
    configure_logging,
    get_logger,
    RequestLoggingMiddleware,
)

# Configure structured logging for Lambda/CloudWatch
# Use JSON format in production, plain text in development
configure_logging(
    level="INFO",
    json_format=app_settings.ENVIRONMENT in ("prod", "staging"),
)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="CICosts API",
    description="Track and optimize your CI/CD costs",
    version="0.1.0",
    docs_url="/docs" if app_settings.ENVIRONMENT != "prod" else None,
    redoc_url="/redoc" if app_settings.ENVIRONMENT != "prod" else None,
    lifespan=lifespan,
)

# CORS configuration
origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://cicosts.dev",
    "https://www.cicosts.dev",
    "https://app.cicosts.dev",
    "https://dev.cicosts.dev",
]

if app_settings.FRONTEND_URL and app_settings.FRONTEND_URL not in origins:
    origins.append(app_settings.FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware (adds request ID and timing)
app.add_middleware(RequestLoggingMiddleware)

# Rate limiting middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(RateLimitMiddleware)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Alerts"])
app.include_router(settings.router, prefix="/api/v1/settings", tags=["Settings"])
app.include_router(billing.router, prefix="/api/v1/billing", tags=["Billing"])
app.include_router(limits.router, prefix="/api/v1/limits", tags=["Limits"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "CICosts API",
        "version": "0.1.0",
        "docs": "/docs" if app_settings.ENVIRONMENT != "prod" else None,
    }
