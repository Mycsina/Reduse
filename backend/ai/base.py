"""Base AI model implementation."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Type

from ..config import settings
from .prompts.base import BasePromptConfig, BasePromptTemplate
from .providers.base import BaseProvider, ProviderError, RateLimitError


@dataclass
class AIModel:
    """Configuration for an AI model with retries."""

    provider: BaseProvider
    config: BasePromptConfig = field(default_factory=BasePromptConfig)
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger(__name__))
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @classmethod
    def from_provider(
        cls,
        provider_class: Type[BaseProvider],
        config: Optional[BasePromptConfig] = None,
    ) -> "AIModel":
        """Create an AI model instance from a provider class."""
        provider = provider_class()
        return cls(
            provider=provider,
            config=config or BasePromptConfig(model_name="", system_prompt=""),
        )

    async def query(
        self,
        prompt: BasePromptTemplate | str,
        max_retries: int = settings.ai.rate_limits["max_retries"],
        **kwargs: Any,
    ) -> Any:
        """Query the model with retries.

        Args:
            prompt: The prompt template or raw string to process
            max_retries: Maximum number of retries on failure
            **kwargs: Additional arguments to format the prompt template

        Returns:
            Dict containing the model response

        Raises:
            ProviderError: If the provider fails to generate a response
            Exception: For other errors after retries exhausted
        """
        # Format prompt if it's a template
        if isinstance(prompt, BasePromptTemplate):
            formatted_prompt = prompt.format(**kwargs)
            config = prompt.get_config()
        else:
            formatted_prompt = prompt
            config = self.config.to_dict()

        retries = 0
        while retries <= max_retries:
            try:
                self.logger.debug(f"Making API call with config: {config}")
                response = await self.provider.generate_json(
                    formatted_prompt,
                    model=config["model"],
                    temperature=config["temperature"],
                    max_tokens=config["max_tokens"],
                )

                self.logger.debug(f"Response: {response}")
                return response

            except RateLimitError as e:
                if retries == max_retries:
                    raise
                wait_time = e.retry_after or 60.0
                self.logger.debug(f"Rate limit exceeded, waiting {wait_time} seconds")
                await asyncio.sleep(wait_time)

            except ProviderError as e:
                if retries == max_retries:
                    raise
                self.logger.debug(f"Provider error: {e}")

            retries += 1

        raise Exception("Max retries exceeded")
