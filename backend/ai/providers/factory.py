"""AI provider factory for creating provider instances."""

from enum import Enum
import logging
from token import OP
from typing import Optional

from ...config import settings, PROVIDER_TYPE
from .base import BaseProvider
from .composite import CompositeProvider
from .google import GoogleAIProvider
from .groq import GroqProvider


def create_provider(provider_type: Optional[PROVIDER_TYPE] = None) -> BaseProvider:
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

    if provider_type == PROVIDER_TYPE.GOOGLE:
        return GoogleAIProvider()
    elif provider_type == PROVIDER_TYPE.GROQ:
        return GroqProvider(api_key=settings.ai.groq_api_key.get_secret_value())
    elif provider_type == PROVIDER_TYPE.COMPOSITE:
        return CompositeProvider()