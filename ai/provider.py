from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class AIProvider(ABC):
    """Abstract base class for AI providers (OpenAI, Google, etc)."""

    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        model: str,
        *,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate a JSON response from the AI model.

        Args:
            prompt: The prompt to send to the model
            model: The specific model to use (e.g. 'gpt-3.5-turbo', 'gemini-pro')
            temperature: Controls randomness in the response (0.0 to 1.0)
            max_tokens: Optional maximum number of tokens to generate

        Returns:
            A JSON string response from the model

        Raises:
            AIProviderError: If the request fails or response is invalid
        """
        pass


class AIProviderError(Exception):
    """Base exception for AI provider errors."""

    pass
