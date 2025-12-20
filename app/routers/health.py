"""
Health check endpoints.

Reference: spec-error-handling.md § 7.2
"""
from fastapi import APIRouter
import httpx

from app.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint.

    Checks:
    - API is responding
    - Database connection via Supabase REST API
    """
    checks = {
        "api": "ok",
        "environment": settings.ENVIRONMENT,
    }

    # Test Supabase connection via REST API (avoids IPv6 issues)
    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.SUPABASE_URL}/rest/v1/",
                    headers={
                        "apikey": settings.SUPABASE_KEY,
                        "Authorization": f"Bearer {settings.SUPABASE_KEY}"
                    },
                    timeout=5.0
                )
                if response.status_code == 200:
                    checks["database"] = "ok"
                else:
                    checks["database"] = f"error: HTTP {response.status_code}"
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
