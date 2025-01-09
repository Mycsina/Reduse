"""Groq AI provider implementation."""

import json
import logging
from typing import Any, Dict, Optional

from groq import AsyncGroq
from groq.types.chat import ChatCompletion
from httpx import HTTPStatusError

from .base import BaseProvider, ProviderError, RateLimitError


class GroqProvider(BaseProvider):
    """Groq AI implementation."""

    def __init__(self, api_key: str):
        """Initialize the Groq provider.

        Args:
            api_key: Groq API key
        """
        super().__init__()
        self.client = AsyncGroq(api_key=api_key)
        self.logger = logging.getLogger(__name__)

    async def generate_text(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text from the model."""
        try:
            response: ChatCompletion = await self.client.chat.completions.create(
                model=model,
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
        model: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate a JSON response using Groq's models."""
        try:
            response: ChatCompletion = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a JSON-only response generator. Always respond with valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},  # Ensure JSON response
            )

            if not response.choices or not response.choices[0].message.content:
                raise ProviderError("Empty response from model")

            return json.loads(response.choices[0].message.content)

        except HTTPStatusError as e:
            if e.response.status_code == 429:
                retry_after = float(e.response.headers.get("retry-after", "60"))
                raise RateLimitError("Rate limit exceeded", retry_after=retry_after)
            raise ProviderError(f"HTTP error: {str(e)}") from e
        except json.JSONDecodeError as e:
            raise ProviderError(f"Invalid JSON response: {e}")
        except Exception as e:
            raise ProviderError(f"Groq error: {str(e)}") from e
