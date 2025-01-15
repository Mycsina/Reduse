"""Base classes for AI providers."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union


class ProviderError(Exception):
    """Base exception for provider errors."""

    pass


class RateLimitError(ProviderError):
    """Raised when provider returns a rate limit response."""

    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class BaseProvider(ABC):
    """Base class for AI providers."""

    def __init__(self):
        """Initialize the provider."""
        self.logger = logging.getLogger(__name__)

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text from the model.

        Args:
            prompt: The input prompt
            model: Model identifier
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text

        Raises:
            ProviderError: If generation fails
            RateLimitError: If rate limit is exceeded
        """
        pass

    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate JSON from the model.

        Args:
            prompt: The input prompt
            model: Model identifier
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated JSON object

        Raises:
            ProviderError: If generation or JSON parsing fails
            RateLimitError: If rate limit is exceeded
        """
        pass

    @abstractmethod
    async def get_embeddings(self, text: Union[str, List[str]]) -> List[List[float]]:
        """Get embeddings for a text or list of texts.

        Args:
            text: A single text string or list of text strings to embed

        Returns:
            A list of embeddings vectors, where each vector is a list of floats.
            If a single text was provided, returns a list with one vector.
            If a list of texts was provided, returns a list with one vector per text.

        Raises:
            ProviderError: If embeddings generation fails
            RateLimitError: If rate limit is exceeded
        """
        pass

    @abstractmethod
    def get_dimensions(self) -> int:
        """Get the dimensionality of the embeddings vectors.

        Returns:
            The number of dimensions in the embeddings vectors.
        """
        pass
