import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..utils.rate_limiter import AIRateLimiter, RateLimitExceeded
from .provider import AIProvider, AIProviderError


@dataclass
class AIModel:
    """Configuration for an AI model with rate limiting and retries."""

    name: str
    provider: AIProvider
    prompt_template: str = "{input}"  # Default to just passing through input
    temperature: float = 0.1
    max_tokens: Optional[int] = None
    rate_limiter: AIRateLimiter = field(default_factory=AIRateLimiter)
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger(__name__))
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def _change_rate_limiter(self, rate_limiter: AIRateLimiter):
        self.rate_limiter = rate_limiter

    async def query(
        self,
        input_text: str,
        max_retries: int = 3,
    ) -> Any:
        """Query the model with rate limiting and retries.

        Args:
            input_text: The input text to process
            max_retries: Maximum number of retries on failure

        Returns:
            Dict containing the model response

        Raises:
            RateLimitExceeded: If rate limits are exceeded and max retries exhausted
            AIProviderError: If the provider fails to generate a response
            Exception: For other errors after retries exhausted
        """
        # Format prompt
        prompt = self.prompt_template.replace("{input}", input_text)

        # Estimate tokens
        token_estimate = self.rate_limiter.estimate_tokens(prompt)
        self.logger.debug(f"Token estimate: {token_estimate}")

        retries = 0
        while retries <= max_retries:
            try:
                # Check and wait for rate limits
                if not await self.rate_limiter.check_limits(self.name, token_estimate):
                    self.logger.debug(f"Rate limit exceeded for {self.name}")
                    await self.rate_limiter.wait_for_rate_limit(self.name)

                # Make the API call
                self.logger.debug(f"Making API call for {self.name}")
                response = await self.provider.generate_json(
                    prompt, model=self.name, temperature=self.temperature, max_tokens=self.max_tokens
                )

                self.logger.debug(f"Response: {response}")

                return response

            except RateLimitExceeded as e:
                if retries == max_retries:
                    raise
                # Wait before retry
                self.logger.debug(f"Rate limit exceeded for {self.name}, waiting {e.wait_time} seconds")
                await asyncio.sleep(e.wait_time)

            except AIProviderError as e:
                if retries == max_retries:
                    raise
                # Retry immediately for provider errors
                self.logger.debug(f"Failed to parse provider response as JSON: {e}")

            retries += 1

        raise Exception("Max retries exceeded")
