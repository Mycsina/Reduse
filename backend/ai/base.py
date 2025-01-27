"""Base AI model implementation."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from .providers.base import BaseProvider, ProviderError, RateLimitError


@dataclass
class AIModel:
    """Configuration for an AI model with retries."""

    name: str
    provider: BaseProvider
    prompt_template: str = "{input}"  # Default to just passing through input
    temperature: float = 0.1
    max_tokens: Optional[int] = None
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger(__name__))
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def query(
        self,
        input_text: str,
        max_retries: int = 3,
    ) -> Any:
        """Query the model with retries.

        Args:
            input_text: The input text to process
            max_retries: Maximum number of retries on failure

        Returns:
            Dict containing the model response

        Raises:
            ProviderError: If the provider fails to generate a response
            Exception: For other errors after retries exhausted
        """
        # Format prompt
        prompt = self.prompt_template.replace("{input}", input_text)

        retries = 0
        while retries <= max_retries:
            try:
                # Make the API call
                self.logger.debug(f"Making API call for {self.name}")
                response = await self.provider.generate_json(
                    prompt, model=self.name, temperature=self.temperature, max_tokens=self.max_tokens
                )

                self.logger.debug(f"Response: {response}")
                return response

            except RateLimitError as e:
                if retries == max_retries:
                    raise
                # Wait for the suggested time before retry
                wait_time = e.retry_after or 60.0
                self.logger.debug(f"Rate limit exceeded for {self.name}, waiting {wait_time} seconds")
                await asyncio.sleep(wait_time)

            except ProviderError as e:
                if retries == max_retries:
                    raise
                # Retry immediately for provider errors
                self.logger.debug(f"Failed to parse provider response as JSON: {e}")

            retries += 1

        raise Exception("Max retries exceeded")
