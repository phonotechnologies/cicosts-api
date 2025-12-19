"""
Health check endpoints.

Reference: spec-error-handling.md § 7.2
"""
from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint.

    Checks:
    - API is responding
    - Database connection (if configured)
    """
    checks = {
        "api": "ok",
        "environment": settings.ENVIRONMENT,
    }

    # Test database connection if configured
    if settings.DATABASE_URL:
        try:
            from app.database import get_engine
            engine = get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as e:
            checks["database"] = f"error: {str(e)[:100]}"
    else:
        checks["database"] = "not_configured"

    # Determine overall status
    status = "ok" if checks.get("database") == "ok" else "degraded"

    return {
        "status": status,
        "checks": checks,
        "version": "0.1.0",
    }


@router.get("/health/ready")
async def readiness_check():
    """Kubernetes-style readiness probe."""
    return {"ready": True}


@router.get("/health/live")
async def liveness_check():
    """Kubernetes-style liveness probe."""
    return {"alive": True}
