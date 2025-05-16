"""AI provider factory for creating provider instances."""

import logging
from typing import Optional

from backend.ai.providers.base import BaseProvider
from backend.ai.providers.google import GoogleAIProvider
from backend.ai.providers.groq import GroqProvider
from backend.config import PROVIDER_TYPE, settings


def create_provider(provider_type: Optional[PROVIDER_TYPE] = None, model: Optional[str] = None) -> BaseProvider:
    """Create a provider instance based on the specified type.

    Args:
        provider_type: The type of provider to create.
                        If None, falls back to the configured default.
        model: The default model to use for the provider.
               If None, uses the provider's default model.

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

    if provider_type == PROVIDER_TYPE.GOOGLE:
        return GoogleAIProvider(default_model=model)
    elif provider_type == PROVIDER_TYPE.GROQ:
        return GroqProvider(api_key=settings.ai.groq_api_key.get_secret_value(), default_model=model)
