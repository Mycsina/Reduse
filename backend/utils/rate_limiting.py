"""Rate limiting middleware and utilities."""

import logging
import time
from typing import Dict, List, Optional, Tuple, Union

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .cache import cache
from .errors import RateLimitError

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiting implementation using Redis."""

    def __init__(
        self, requests_per_minute: int = 60, burst_requests: Optional[int] = None, key_prefix: str = "ratelimit"
    ):
        """Initialize the rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute
            burst_requests: Maximum burst requests (defaults to 2x requests_per_minute)
            key_prefix: Redis key prefix for rate limit counters
        """
        self.requests_per_minute = requests_per_minute
        self.burst_requests = burst_requests or (requests_per_minute * 2)
        self.key_prefix = key_prefix
        self.logger = logging.getLogger(__name__)

    async def is_rate_limited(self, key: str) -> Tuple[bool, Dict[str, Union[int, float]]]:
        """Check if a key is rate limited.

        Args:
            key: Identifier for the client (e.g., IP address, API key)

        Returns:
            Tuple of (is_limited, rate_info)
        """
        # Get the current minute window
        current_minute = int(time.time() / 60)

        # Define Redis keys for the current and previous minute
        current_key = f"{self.key_prefix}:{key}:{current_minute}"
        previous_key = f"{self.key_prefix}:{key}:{current_minute - 1}"

        # Get current counts
        current_count = await cache.increment(current_key, 1)

        # Set expiration for 2 minutes (to ensure cleanup)
        await cache.redis.expire(current_key, 120)

        # Get previous minute's count
        previous_count = await cache.get(previous_key)
        previous_count = int(previous_count) if previous_count else 0

        # Calculate the rate
        current_rate = current_count
        weighted_rate = current_count + (previous_count * 0.5)  # Half weight for previous minute

        # Check if rate limited
        is_limited = weighted_rate > self.burst_requests

        # Prepare rate info
        rate_info = {
            "current_rate": current_rate,
            "weighted_rate": weighted_rate,
            "limit": self.requests_per_minute,
            "burst_limit": self.burst_requests,
            "remaining": max(0, self.burst_requests - weighted_rate),
            "reset_at": (current_minute + 1) * 60,
            "retry_after": (current_minute + 1) * 60 - int(time.time()) if is_limited else 0,
        }

        return is_limited, rate_info


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for enforcing rate limits on requests."""

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        burst_requests: Optional[int] = None,
        exclude_paths: Optional[List[str]] = None,
        api_key_header: str = "X-API-Key",
    ):
        """Initialize the rate limit middleware.

        Args:
            app: The FastAPI application
            requests_per_minute: Maximum requests per minute
            burst_requests: Maximum burst requests
            exclude_paths: Paths to exclude from rate limiting
            api_key_header: Header name for API key
        """
        super().__init__(app)
        self.rate_limiter = RateLimiter(requests_per_minute=requests_per_minute, burst_requests=burst_requests)
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/openapi.json"]
        self.api_key_header = api_key_header
        self.logger = logging.getLogger(__name__)

    async def dispatch(self, request: Request, call_next: callable) -> Response:
        """Process the request with rate limiting.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            The response
        """
        # Skip rate limiting for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Determine rate limit key (API key or IP)
        key = request.headers.get(self.api_key_header)
        if not key:
            key = f"ip:{request.client.host}" if request.client else "ip:unknown"

        # Check rate limit
        is_limited, rate_info = await self.rate_limiter.is_rate_limited(key)

        # Set rate limit headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.rate_limiter.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(int(rate_info["remaining"]))
        response.headers["X-RateLimit-Reset"] = str(int(rate_info["reset_at"]))

        # If rate limited, return 429 response
        if is_limited:
            self.logger.warning(f"Rate limit exceeded for {key}", extra={"key": key, "rate_info": rate_info})
            response.headers["Retry-After"] = str(int(rate_info["retry_after"]))
            error = RateLimitError("Rate limit exceeded", str(key))
            response.status_code = 429
            # Don't reset response body here to avoid breaking streaming responses

        return response
