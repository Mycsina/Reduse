import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional


class RateLimitExceeded(Exception):
    """Raised when rate limits are exceeded."""

    def __init__(self, message: str, wait_time: float):
        super().__init__(message)
        self.wait_time = wait_time


@dataclass
class RateLimit:
    max_requests_per_minute: int
    max_tokens_per_minute: int
    max_requests_per_day: int
    current_minute_requests: int = 0
    current_minute_tokens: int = 0
    current_day_requests: int = 0
    last_minute_reset: float = time.time()
    last_day_reset: datetime = datetime.now()
    last_request_time: float = time.time()


class AIRateLimiter:
    """Rate limiter for AI API calls with usage header tracking."""

    def __init__(
        self,
        rpm_limit: int = 10,
        tpm_limit: int = 4_000_000,  # Gemini default limit
        rpd_limit: int = 1500,
    ):
        self.limits: Dict[str, RateLimit] = {}
        self.default_limits = {
            "rpm": rpm_limit,
            "tpm": tpm_limit,
            "rpd": rpd_limit,
        }
        self._lock = asyncio.Lock()
        self.logger = logging.getLogger(__name__)

    async def check_limits(self, model_name: str, token_count: Optional[int] = None) -> bool:
        """Check if the request can proceed under current rate limits.

        Returns:
            bool: True if request can proceed, False if rate limited
        """
        async with self._lock:
            if model_name not in self.limits:
                self.limits[model_name] = RateLimit(
                    max_requests_per_minute=self.default_limits["rpm"],
                    max_tokens_per_minute=self.default_limits["tpm"],
                    max_requests_per_day=self.default_limits["rpd"],
                )

            limit = self.limits[model_name]
            current_time = time.time()
            current_date = datetime.now()

            # Reset minute counters if needed
            if current_time - limit.last_minute_reset >= 60:
                limit.current_minute_requests = 0
                limit.current_minute_tokens = 0
                limit.last_minute_reset = current_time

            # Reset daily counter if needed
            if current_date.date() > limit.last_day_reset.date():
                limit.current_day_requests = 0
                limit.last_day_reset = current_date

            # Check limits
            if limit.current_minute_requests >= limit.max_requests_per_minute:
                return False

            if limit.current_day_requests >= limit.max_requests_per_day:
                return False

            if token_count and limit.current_minute_tokens + token_count > limit.max_tokens_per_minute:
                return False

            # Update counters
            limit.current_minute_requests += 1
            limit.current_day_requests += 1
            if token_count:
                limit.current_minute_tokens += token_count

            limit.last_request_time = current_time
            return True

    async def wait_for_rate_limit(self, model_name: str) -> None:
        """Wait until rate limits allow another request."""
        self.logger.debug(f"Waiting for rate limit for {model_name}, acquiring lock")
        async with self._lock:
            if model_name not in self.limits:
                return

            limit = self.limits[model_name]
            current_time = time.time()

            # Calculate wait time based on minute limits
            minute_wait = max(0, 60 - (current_time - limit.last_minute_reset))

            # Calculate wait time based on daily limits
            current_date = datetime.now()
            if current_date.date() > limit.last_day_reset.date():
                day_wait = 0
            else:
                next_reset = (limit.last_day_reset + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                day_wait = (next_reset - current_date).total_seconds()

            # Take the maximum wait time needed
            wait_time = max(minute_wait, day_wait)

            if wait_time > 0:
                self.logger.debug(f"Waiting for {wait_time} seconds for {model_name}")
                await asyncio.sleep(wait_time)

    def update_from_headers(self, model_name: str, headers: Dict[str, str]) -> None:
        """Update rate limits based on API response headers."""
        if model_name not in self.limits:
            return

        limit = self.limits[model_name]

        # Update limits from headers if provided
        if "x-ratelimit-remaining-requests" in headers:
            remaining_requests = int(headers["x-ratelimit-remaining-requests"])
            limit.current_minute_requests = limit.max_requests_per_minute - remaining_requests
            self.logger.debug(f"Updated remaining requests for {model_name}: {limit.current_minute_requests}")

        if "x-ratelimit-remaining-tokens" in headers:
            remaining_tokens = int(headers["x-ratelimit-remaining-tokens"])
            limit.current_minute_tokens = limit.max_tokens_per_minute - remaining_tokens
            self.logger.debug(f"Updated remaining tokens for {model_name}: {limit.current_minute_tokens}")

    @classmethod
    def estimate_tokens(cls, text: str) -> int:
        """Rough estimate of token count (4 chars per token)"""
        return len(text) // 4

    def get_rpm_remaining(self, model_name: str = "default") -> int:
        """Get remaining requests per minute for a model."""
        if model_name not in self.limits:
            return self.default_limits["rpm"]

        limit = self.limits[model_name]
        current_time = time.time()

        # Reset if minute has passed
        if current_time - limit.last_minute_reset >= 60:
            return limit.max_requests_per_minute

        return max(0, limit.max_requests_per_minute - limit.current_minute_requests)

    def get_rpd_remaining(self, model_name: str = "default") -> int:
        """Get remaining requests per day for a model."""
        if model_name not in self.limits:
            return self.default_limits["rpd"]

        limit = self.limits[model_name]
        current_date = datetime.now()

        # Reset if day has passed
        if current_date.date() > limit.last_day_reset.date():
            return limit.max_requests_per_day

        return max(0, limit.max_requests_per_day - limit.current_day_requests)
