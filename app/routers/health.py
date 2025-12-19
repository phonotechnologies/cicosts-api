"""
Health check endpoints.

Reference: spec-error-handling.md § 7.2
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.config import settings

router = APIRouter()


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint.

    Checks:
    - API is responding
    - Database connection
    """
    checks = {
        "api": "ok",
        "database": "ok",
        "environment": settings.ENVIRONMENT,
    }

    # Test database connection
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        checks["database"] = f"error: {str(e)[:100]}"

    # Determine overall status
    status = "ok" if all(
        v == "ok" or k in ["environment"]
        for k, v in checks.items()
    ) else "degraded"

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
