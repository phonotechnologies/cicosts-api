"""
Rate limiting middleware for CICosts API.

Implements tier-based rate limits:
- Free: 60 requests/minute
- Pro: 300 requests/minute
- Team: 600 requests/minute

Uses in-memory storage by default (resets on Lambda cold start).
Can be configured to use Redis for distributed rate limiting.
"""
import logging
from typing import Optional, Callable
from uuid import UUID

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Rate limits per tier (requests per minute)
TIER_RATE_LIMITS = {
    "free": "60/minute",
    "pro": "300/minute",
    "team": "600/minute",
}

# Default rate limit for unauthenticated requests
DEFAULT_RATE_LIMIT = "30/minute"

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


# Create limiter instance with in-memory storage
# Note: For Lambda, this resets on cold starts. Use Redis for production.
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[DEFAULT_RATE_LIMIT],
    storage_uri="memory://",
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Handle rate limit exceeded errors."""
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
    Middleware to apply tier-based rate limiting.

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

        # Get the rate limit key
        key = get_rate_limit_key(request)

        # Get the tier-based rate limit
        tier = get_tier_from_request(request)
        rate_limit = TIER_RATE_LIMITS.get(tier, DEFAULT_RATE_LIMIT)

        # Check if rate limited
        # Note: In production, you'd check against Redis here
        # For now, we'll add headers but not block (see below for enforcement)

        # Add rate limit headers to response
        response = await call_next(request)

        # Add informational headers
        response.headers["X-RateLimit-Tier"] = tier
        response.headers["X-RateLimit-Limit"] = rate_limit

        return response


def apply_rate_limit(tier: str = "free"):
    """
    Decorator to apply rate limiting to specific endpoints.

    Usage:
        @router.get("/endpoint")
        @limiter.limit(dynamic_limit_provider)
        async def endpoint(...):
            ...
    """
    return limiter.limit(TIER_RATE_LIMITS.get(tier, DEFAULT_RATE_LIMIT))


def get_dynamic_limit(key: str) -> str:
    """
    Get dynamic rate limit based on tier.

    This function is called by slowapi to determine the rate limit.
    """
    # Parse the tier from the key or use default
    # In practice, you'd look up the org's tier from the database
    return DEFAULT_RATE_LIMIT
