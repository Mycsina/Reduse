"""AI provider factory for creating provider instances."""

import logging
from typing import Optional

from ...config import settings
from .base import BaseProvider
from .google import GoogleAIProvider
from .groq import GroqProvider
from .composite import CompositeProvider


class AIProviderFactory:
    """Factory for creating AI provider instances."""

    @staticmethod
    def create_provider(provider_type: Optional[str] = None) -> BaseProvider:
        """Create a provider instance based on the specified type.

        Args:
            provider_type: The type of provider to create.
                           If None, falls back to the configured default.

        Returns:
            An instance of the specified provider type

        Raises:
            ValueError: If the specified provider type is not supported
        """
        logger = logging.getLogger(__name__)

        # If no type specified, use the default from configuration
        if not provider_type:
            provider_type = settings.ai.default_provider
            logger.debug(f"Using default provider: {provider_type}")

        logger.debug(f"Creating provider: {provider_type}")

        if provider_type == "google":
            return GoogleAIProvider()
        elif provider_type == "groq":
            return GroqProvider(api_key=settings.ai.groq_api_key.get_secret_value())
        elif provider_type == "composite":
            return CompositeProvider()
        else:
            logger.error(f"Unsupported provider type: {provider_type}")
            raise ValueError(f"Unsupported provider type: {provider_type}")
