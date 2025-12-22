"""
Redis-based rate limiter using Upstash.

Implements sliding window rate limiting with tier-based limits.
Falls back to allowing requests if Redis is unavailable.
"""
import logging
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from upstash_redis import Redis

from app.config import get_upstash_secrets

logger = logging.getLogger(__name__)

# Rate limits per tier (requests per minute)
TIER_RATE_LIMITS = {
    "free": 60,
    "pro": 300,
    "team": 600,
}

# Default rate limit for unauthenticated requests
DEFAULT_RATE_LIMIT = 30

# Window size in seconds (1 minute)
WINDOW_SIZE = 60


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    limit: int
    remaining: int
    reset_at: int  # Unix timestamp
    retry_after: Optional[int] = None  # Seconds until retry allowed


class RedisRateLimiter:
    """
    Redis-based rate limiter using Upstash.

    Uses sliding window algorithm for accurate rate limiting.
    Falls back to allowing requests if Redis is unavailable.
    """

    _instance: Optional["RedisRateLimiter"] = None
    _redis: Optional[Redis] = None
    _initialized: bool = False

    def __new__(cls) -> "RedisRateLimiter":
        """Singleton pattern for rate limiter."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _ensure_initialized(self) -> bool:
        """Initialize Redis connection if not already done."""
        if self._initialized:
            return self._redis is not None

        self._initialized = True

        try:
            secrets = get_upstash_secrets()
            url = secrets.get("url")
            token = secrets.get("token")

            if not url or not token:
                logger.warning("Upstash Redis not configured - rate limiting will be permissive")
                return False

            self._redis = Redis(url=url, token=token)

            # Test connection
            self._redis.ping()
            logger.info("Upstash Redis connected successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Upstash Redis: {e}")
            self._redis = None
            return False

    def check_rate_limit(
        self,
        key: str,
        tier: str = "free"
    ) -> RateLimitResult:
        """
        Check if a request is within rate limits.

        Uses sliding window algorithm:
        1. Get current window start time
        2. Remove expired entries
        3. Count requests in current window
        4. Allow if under limit, deny if over

        Args:
            key: Unique identifier (e.g., "org:uuid", "user:uuid", "ip:1.2.3.4")
            tier: Subscription tier (free, pro, team)

        Returns:
            RateLimitResult with allowed status and limit info
        """
        limit = TIER_RATE_LIMITS.get(tier, DEFAULT_RATE_LIMIT)
        now = int(time.time())
        window_start = now - WINDOW_SIZE
        reset_at = now + WINDOW_SIZE

        # If Redis not available, allow request
        if not self._ensure_initialized() or self._redis is None:
            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=limit - 1,
                reset_at=reset_at,
            )

        redis_key = f"ratelimit:{key}"

        try:
            # Use pipeline for atomic operations
            pipe = self._redis.pipeline()

            # Remove old entries outside the window
            pipe.zremrangebyscore(redis_key, 0, window_start)

            # Count current requests in window
            pipe.zcard(redis_key)

            # Add current request with timestamp as score
            request_id = f"{now}:{id(self)}"
            pipe.zadd(redis_key, {request_id: now})

            # Set expiry on the key
            pipe.expire(redis_key, WINDOW_SIZE + 10)

            # Execute pipeline
            results = pipe.exec()

            # results[1] is the count before adding current request
            current_count = results[1] if results[1] else 0

            if current_count >= limit:
                # Over limit - remove the request we just added
                self._redis.zrem(redis_key, request_id)

                # Calculate retry after
                oldest = self._redis.zrange(redis_key, 0, 0, withscores=True)
                if oldest:
                    oldest_time = int(oldest[0][1])
                    retry_after = max(1, oldest_time + WINDOW_SIZE - now)
                else:
                    retry_after = WINDOW_SIZE

                return RateLimitResult(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_at=reset_at,
                    retry_after=retry_after,
                )

            remaining = max(0, limit - current_count - 1)

            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=remaining,
                reset_at=reset_at,
            )

        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            # Fail open - allow request if Redis fails
            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=limit - 1,
                reset_at=reset_at,
            )

    def get_usage(self, key: str) -> Tuple[int, int]:
        """
        Get current usage for a key.

        Returns:
            Tuple of (current_count, window_remaining_seconds)
        """
        if not self._ensure_initialized() or self._redis is None:
            return (0, WINDOW_SIZE)

        redis_key = f"ratelimit:{key}"
        now = int(time.time())
        window_start = now - WINDOW_SIZE

        try:
            # Remove expired and count
            self._redis.zremrangebyscore(redis_key, 0, window_start)
            count = self._redis.zcard(redis_key) or 0

            # Get oldest entry to calculate window remaining
            oldest = self._redis.zrange(redis_key, 0, 0, withscores=True)
            if oldest:
                oldest_time = int(oldest[0][1])
                remaining = max(0, oldest_time + WINDOW_SIZE - now)
            else:
                remaining = WINDOW_SIZE

            return (count, remaining)

        except Exception as e:
            logger.error(f"Failed to get rate limit usage: {e}")
            return (0, WINDOW_SIZE)

    def reset(self, key: str) -> bool:
        """
        Reset rate limit for a key.

        Useful for testing or manual intervention.
        """
        if not self._ensure_initialized() or self._redis is None:
            return False

        redis_key = f"ratelimit:{key}"

        try:
            self._redis.delete(redis_key)
            return True
        except Exception as e:
            logger.error(f"Failed to reset rate limit: {e}")
            return False

    def is_healthy(self) -> bool:
        """Check if Redis connection is healthy."""
        if not self._ensure_initialized() or self._redis is None:
            return False

        try:
            self._redis.ping()
            return True
        except Exception:
            return False


# Singleton instance
rate_limiter = RedisRateLimiter()
