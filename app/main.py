"""
CICosts API - FastAPI Application

Main entry point for the API.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import health, auth, webhooks


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
    docs_url="/docs" if settings.ENVIRONMENT != "prod" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "prod" else None,
    lifespan=lifespan,
)

# CORS configuration
origins = [
    "http://localhost:3000",
    "https://cicosts.dev",
    "https://www.cicosts.dev",
]

if settings.FRONTEND_URL:
    origins.append(settings.FRONTEND_URL)

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


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "CICosts API",
        "version": "0.1.0",
        "docs": "/docs" if settings.ENVIRONMENT != "prod" else None,
    }
