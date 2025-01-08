import logging
import re
from typing import Dict, Any, Optional
import json
import google.generativeai as genai
from .provider import AIProvider, AIProviderError


class GoogleAIProvider(AIProvider):
    """Provider for Google's Generative AI API."""

    logger = logging.getLogger(__name__)

    def __init__(self, api_key: str):
        """Initialize the Google AI provider.

        Args:
            api_key: Google AI API key
        """
        # Configure the API
        genai.configure(api_key=api_key)
        self._models = {}  # Cache for initialized models

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
            model: The specific model to use (e.g. 'gemini-pro')
            temperature: Controls randomness in the response (0.0 to 1.0)
            max_tokens: Optional maximum number of tokens to generate

        Returns:
            A JSON string response from the model

        Raises:
            AIProviderError: If the request fails or response is invalid
        """
        # Add explicit JSON formatting instruction
        json_prompt = f"""You must respond with a valid JSON object only.
Do not include any explanatory text, markdown formatting, or code blocks.
The response should be parseable by json.loads().

{prompt}"""

        # Get response from model
        model_instance = self._get_model(model, temperature, max_tokens)
        response = await model_instance.generate_content_async(json_prompt)

        if not response.text:
            raise AIProviderError("Empty response from model")

        # We must remove markdown formatting from the response
        response_text = response.text
        if response_text.startswith("```json"):
            # Get all text after the first line
            response_text = response_text.split("```json\n", maxsplit=1)[1]
        if response_text.endswith("```\n"):
            # Get all text before the last line
            response_text = response_text.rsplit("```\n", maxsplit=1)[0]

        # Parse response as JSON
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            self.logger.error(f"Couldn't parse JSON from model response: {response_text}")
            raise AIProviderError(f"Invalid JSON response: {e}")
