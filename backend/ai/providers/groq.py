"""Groq AI provider implementation."""

import json
import logging
from typing import Any, Dict, List, Optional, Union

from groq import AsyncGroq
from groq.types.chat import ChatCompletion
from httpx import HTTPStatusError

from backend.ai.providers.base import BaseProvider
from backend.utils.errors import ProviderError, RateLimitError


class GroqProvider(BaseProvider):
    """Groq AI implementation."""

    def __init__(self, api_key: str, default_model: Optional[str] = None):
        """Initialize the Groq provider.

        Args:
            api_key: Groq API key
            default_model: The default model to use for text generation. If None, uses the configured default.
        """
        super().__init__(default_model=default_model)
        self.client = AsyncGroq(api_key=api_key)
        self.model = default_model or "llama-3.1-8b-instant"
        self._dimensions = 768  # Same as Gemini for compatibility
        self.logger = logging.getLogger(__name__)
        self.provider = "groq"

    async def generate_text(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text from the model."""
        try:
            response: ChatCompletion = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            if not response.choices or not response.choices[0].message.content:
                raise ProviderError("Empty response from model")

            return response.choices[0].message.content

        except HTTPStatusError as e:
            if e.response.status_code == 429:
                retry_after = float(e.response.headers.get("retry-after", "60"))
                raise RateLimitError("Rate limit exceeded", retry_after=retry_after)
            raise ProviderError(f"HTTP error: {str(e)}") from e
        except Exception as e:
            raise ProviderError(f"Groq error: {str(e)}") from e

    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate JSON from the model.

        Args:
            prompt: The input prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated JSON object
        """
        json_prompt = f"""You must respond with a valid JSON object only.
Do not include any explanatory text, markdown formatting, or code blocks.
The response should be parseable by json.loads().

{prompt}"""
        try:
            response: ChatCompletion = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": json_prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            if not response.choices or not response.choices[0].message.content:
                raise ProviderError("Empty response from model")

            # Parse the JSON response
            try:
                return json.loads(response.choices[0].message.content)
            except json.JSONDecodeError as e:
                raise ProviderError(f"Failed to parse JSON response: {str(e)}")

        except HTTPStatusError as e:
            if e.response.status_code == 429:
                retry_after = float(e.response.headers.get("retry-after", "60"))
                raise RateLimitError("Rate limit exceeded", retry_after=retry_after)
            raise ProviderError(f"HTTP error: {str(e)}") from e
        except Exception as e:
            raise ProviderError(f"Groq error: {str(e)}") from e

    async def get_embeddings(self, text: Union[str, List[str]]) -> List[List[float]]:
        """Get embeddings for a text or list of texts.

        Note: Groq does not currently support embeddings, so this is a fallback implementation
        that returns zero vectors. This allows the system to continue functioning even if
        embeddings are requested from Groq, though the results will not be meaningful.

        Args:
            text: A single text string or list of text strings to embed

        Returns:
            A list of zero vectors with the same dimensions as Gemini embeddings
        """
        # Convert single text to list for uniform processing
        raise NotImplementedError("Groq does not support embeddings")

    def get_dimensions(self) -> int:
        """Get the dimensionality of the embeddings vectors.

        Returns:
            Number of dimensions (768 for compatibility with Gemini)
        """
        raise NotImplementedError("Groq does not support embeddings")
