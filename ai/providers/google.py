"""Google AI provider implementation."""

import json
import logging
from typing import Any, Dict, Optional

import google.generativeai as genai
from google.api_core import exceptions

from .base import BaseProvider, ProviderError, RateLimitError


class GoogleAIProvider(BaseProvider):
    """Provider for Google's Generative AI API (including Gemini)."""

    def __init__(self, api_key: str):
        """Initialize the Google AI provider.

        Args:
            api_key: Google AI API key
        """
        super().__init__()
        genai.configure(api_key=api_key)
        self._models = {}  # Cache for initialized models
        self.logger = logging.getLogger(__name__)

    def _get_model(self, model: str, temperature: float, max_tokens: Optional[int]) -> genai.GenerativeModel:
        """Get or create a model instance with the specified parameters."""
        key = (model, temperature, max_tokens)
        if key not in self._models:
            config = {
                "temperature": temperature,
                "top_p": 0.95,
                "top_k": 40,
            }
            if max_tokens:
                config["max_output_tokens"] = max_tokens

            self._models[key] = genai.GenerativeModel(
                model_name=model, generation_config=genai.types.GenerationConfig(**config)
            )
        return self._models[key]

    async def generate_text(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text from the model."""
        try:
            model_instance = self._get_model(model, temperature, max_tokens)
            response = await model_instance.generate_content_async(prompt)

            if not response.text:
                raise ProviderError("Empty response from model")

            return response.text

        except exceptions.ResourceExhausted as e:
            # Google's API returns 429 as ResourceExhausted
            # Default to 60s retry if no retry info provided
            raise RateLimitError(str(e), retry_after=60.0)
        except Exception as e:
            raise ProviderError(f"Google error: {str(e)}") from e

    async def generate_json(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate a JSON response from the AI model."""
        # Add explicit JSON formatting instruction
        json_prompt = f"""You must respond with a valid JSON object only.
Do not include any explanatory text, markdown formatting, or code blocks.
The response should be parseable by json.loads().

{prompt}"""

        try:
            # Get response from model
            model_instance = self._get_model(model, temperature, max_tokens)
            response = await model_instance.generate_content_async(json_prompt)

            if not response.text:
                raise ProviderError("Empty response from model")

            # Clean up markdown formatting if present
            response_text = response.text
            if response_text.startswith("```json"):
                response_text = response_text.split("```json\n", maxsplit=1)[1]
            if response_text.endswith(("```", "```\n")):
                response_text = response_text.rsplit("```", maxsplit=1)[0]

            # Parse response as JSON
            try:
                return json.loads(response_text)
            except json.JSONDecodeError as e:
                self.logger.error(f"Couldn't parse JSON from model response: {response_text}")
                raise ProviderError(f"Invalid JSON response: {e}")

        except exceptions.ResourceExhausted as e:
            # Google's API returns 429 as ResourceExhausted
            # Default to 60s retry if no retry info provided
            raise RateLimitError(str(e), retry_after=60.0)
        except Exception as e:
            raise ProviderError(f"Google error: {str(e)}") from e
