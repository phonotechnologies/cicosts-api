"""
CICosts API - FastAPI Application

Main entry point for the API.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings as app_settings
from app.routers import health, auth, webhooks, dashboard, alerts, settings, billing


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

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Alerts"])
app.include_router(settings.router, prefix="/api/v1/settings", tags=["Settings"])
app.include_router(billing.router, prefix="/api/v1/billing", tags=["Billing"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "CICosts API",
        "version": "0.1.0",
        "docs": "/docs" if app_settings.ENVIRONMENT != "prod" else None,
    }
