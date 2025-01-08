"""Groq AI provider implementation."""

from typing import Optional
from groq import AsyncGroq
from groq.types.chat import ChatCompletion

from .provider import AIProvider, AIProviderError


class GroqProvider(AIProvider):
    """Groq AI implementation."""

    def __init__(self, api_key: str):
        self.client = AsyncGroq(api_key=api_key)

    async def generate_json(
        self,
        prompt: str,
        model: str,
        *,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> str:
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
                raise AIProviderError("Empty response from model")

            return response.choices[0].message.content

        except Exception as e:
            raise AIProviderError(f"Groq error: {str(e)}") from e
