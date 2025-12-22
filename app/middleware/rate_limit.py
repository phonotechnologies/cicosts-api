"""
Rate limiting middleware for CICosts API.

Implements tier-based rate limits using Upstash Redis:
- Free: 60 requests/minute
- Pro: 300 requests/minute
- Team: 600 requests/minute

Uses Redis for distributed rate limiting across Lambda instances.
Falls back to allowing requests if Redis is unavailable.
"""
import logging
from typing import Callable

from fastapi import Request, Response
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.services.redis_rate_limiter import rate_limiter, TIER_RATE_LIMITS, DEFAULT_RATE_LIMIT

logger = logging.getLogger(__name__)

# Exempt paths (webhooks, health checks)
EXEMPT_PATHS = [
    "/health",
    "/api/v1/webhooks/github",
    "/api/v1/webhooks/stripe",
]


def get_rate_limit_key(request: Request) -> str:
    """
    Get rate limit key based on user/org or IP.

    Priority:
    1. Org ID from query params (for authenticated org-scoped requests)
    2. User ID from JWT token
    3. IP address (fallback for unauthenticated)
    """
    # Try to get org_id from query params
    org_id = request.query_params.get("org_id")
    if org_id:
        return f"org:{org_id}"

    # Try to get user_id from request state (set by auth dependency)
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"

    # Fall back to IP address
    return f"ip:{get_remote_address(request)}"


def get_tier_from_request(request: Request) -> str:
    """
    Get subscription tier from request state.

    This is set by the auth dependency after validating the token.
    Returns 'free' if not set.
    """
    return getattr(request.state, "tier", "free")


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Handle rate limit exceeded errors (for slowapi compatibility)."""
    logger.warning(
        f"Rate limit exceeded for {get_rate_limit_key(request)}: {exc.detail}"
    )
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please try again later.",
            "retry_after": str(exc.detail).split(" per ")[0] if exc.detail else "60",
        },
        headers={
            "Retry-After": "60",
            "X-RateLimit-Limit": str(exc.detail) if exc.detail else "unknown",
        },
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to apply tier-based rate limiting using Redis.

    Rate limits are applied based on the organization's subscription tier.
    Webhooks and health checks are exempt.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for exempt paths
        if any(request.url.path.startswith(path) for path in EXEMPT_PATHS):
            return await call_next(request)

        # Skip rate limiting for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Get the rate limit key and tier
        key = get_rate_limit_key(request)
        tier = get_tier_from_request(request)

        # Check rate limit using Redis
        result = rate_limiter.check_rate_limit(key, tier)

        if not result.allowed:
            logger.warning(
                f"Rate limit exceeded for {key} (tier: {tier}, limit: {result.limit}/min)"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": result.retry_after or 60,
                },
                headers={
                    "Retry-After": str(result.retry_after or 60),
                    "X-RateLimit-Limit": str(result.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(result.reset_at),
                    "X-RateLimit-Tier": tier,
                },
            )

        # Process the request
        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_at)
        response.headers["X-RateLimit-Tier"] = tier

        return response


def get_rate_limit_for_tier(tier: str) -> str:
    """Get the rate limit string for a tier (for documentation)."""
    limit = TIER_RATE_LIMITS.get(tier, DEFAULT_RATE_LIMIT)
    return f"{limit}/minute"
