"""Google AI provider implementation."""

import asyncio
import json
import logging
from functools import partial
from typing import Any, Dict, List, Optional, Union

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
        self._dimensions = 768  # Gemini embedding model has 768 dimensions
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

    async def get_embeddings(self, text: Union[str, List[str]]) -> List[List[float]]:
        """Get embeddings using Google's embedding model.

        Args:
            text: Text or list of texts to embed

        Returns:
            List of embeddings vectors
        """
        try:
            # Convert single text to list for uniform processing
            texts = [text] if isinstance(text, str) else text
            self.logger.debug(f"Getting embeddings for {len(texts)} texts")

            # Get embeddings for each text
            embeddings = []
            for i, t in enumerate(texts, 1):
                # Clean and truncate text if needed
                cleaned_text = self._clean_text(t)
                self.logger.debug(
                    f"Text {i}/{len(texts)} - Original length: {len(t)}, " f"Cleaned length: {len(cleaned_text)}"
                )

                # Get embeddings from model using sync API in async wrapper
                self.logger.debug(f"Requesting embeddings for text {i}/{len(texts)}")
                loop = asyncio.get_event_loop()
                try:
                    result = await loop.run_in_executor(
                        None,
                        partial(
                            genai.embed_content,
                            model="models/embedding-001",
                            content=cleaned_text,
                            task_type="retrieval_document",
                        ),
                    )
                    self.logger.debug(f"Successfully got embeddings for text {i}/{len(texts)}")

                    if not result or "embedding" not in result:
                        raise ProviderError(f"No embedding returned from model for text {i}")

                    embedding = list(result["embedding"])
                    self.logger.debug(f"Text {i}/{len(texts)} - Got embedding with {len(embedding)} dimensions")
                    embeddings.append(embedding)

                except Exception as e:
                    self.logger.error(
                        f"Failed to get embeddings for text {i}/{len(texts)}: {str(e)}\n"
                        f"Text preview: {cleaned_text[:100]}..."
                    )
                    raise

            self.logger.debug(
                f"Successfully generated embeddings for {len(embeddings)} texts "
                f"with {len(embeddings[0]) if embeddings else 0} dimensions"
            )
            return embeddings

        except exceptions.ResourceExhausted as e:
            # Google's API returns 429 as ResourceExhausted
            self.logger.warning(f"Rate limit exceeded: {str(e)}")
            raise RateLimitError(str(e), retry_after=60.0)
        except Exception as e:
            self.logger.error(f"Error getting embeddings from Google: {str(e)}")
            # Return zero vectors as fallback
            dims = self.get_dimensions()
            count = 1 if isinstance(text, str) else len(text)
            self.logger.info(f"Returning {count} zero vectors with {dims} dimensions as fallback")
            return [[0.0] * dims] * count

    def get_dimensions(self) -> int:
        """Get the dimensionality of the embeddings vectors.

        Returns:
            Number of dimensions (768 for Gemini embedding model)
        """
        return self._dimensions

    def _clean_text(self, text: str) -> str:
        """Clean text before embedding.

        Args:
            text: Text to clean

        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = " ".join(text.split())

        # Truncate if too long (model has a token limit)
        max_chars = 3000  # Approximate limit
        if len(text) > max_chars:
            text = text[:max_chars]

        return text
