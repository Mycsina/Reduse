"""Google AI provider implementation."""

import asyncio
import json
import logging
from functools import partial
from typing import Any, Dict, List, Optional, Set, Union

import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import TaskType
from google.api_core import exceptions
from tqdm import tqdm

from ...config import settings
from ...utils.errors import ProviderError, RateLimitError
from .base import BaseProvider


class GoogleAIProvider(BaseProvider):
    """Provider for Google's Generative AI API (including Gemini)."""

    def __init__(self, default_model: Optional[str] = None):
        """Initialize the Google AI provider.

        Args:
            default_model: The default model to use for text generation. If None, uses the configured default.
        """
        super().__init__(default_model=default_model)
        genai.configure(api_key=settings.ai.google_api_key.get_secret_value())
        self._dimensions = 768  # Using models/text-embedding-004 model
        self._default_model = default_model or settings.ai.default_model
        self.logger = logging.getLogger(__name__)

    async def generate_text(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text from the model."""
        generate_config = genai.types.GenerationConfig(temperature=temperature, max_output_tokens=max_tokens)
        try:
            model_instance = genai.GenerativeModel(model_name=self._default_model, generation_config=generate_config)
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
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate a JSON response from the AI model."""
        # Add explicit JSON formatting instruction
        json_prompt = f"""You must respond with a valid JSON object only.
Do not include any explanatory text, markdown formatting, or code blocks.
The response should be parseable by json.loads().

{prompt}"""
        generate_config = genai.types.GenerationConfig(temperature=temperature, max_output_tokens=max_tokens)
        try:
            # Get response from model
            model_instance = genai.GenerativeModel(model_name=self._default_model, generation_config=generate_config)
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

    async def get_embeddings(
        self,
        text: Union[str, List[str]],
        task_type: TaskType = TaskType.CLASSIFICATION,
        max_batch_retries: int = 5,  # Maximum retries for failed entries
        base_batch_delay: float = 30.0,  # Initial delay for rate limit cooldown
    ) -> List[List[float]]:
        """Get embeddings using Google's embedding model.

        Args:
            text: Text or list of texts to embed
            task_type: Task type for the embedding
            max_batch_retries: Maximum number of retries for failed entries
            base_batch_delay: Initial delay in seconds between retries
        Returns:
            List of embeddings vectors
        """
        texts = [text] if isinstance(text, str) else text
        self.logger.debug(f"Getting embeddings for {len(texts)} texts")

        # Track results and failures
        results: Dict[int, List[float]] = {}  # Index -> embedding
        failed_indices: Set[int] = set(range(len(texts)))  # Start with all indices as failed
        retry_count = 0
        current_delay = base_batch_delay

        while failed_indices and retry_count < max_batch_retries:
            if retry_count > 0:
                self.logger.warning(
                    f"Rate limit hit. Retrying {len(failed_indices)} failed texts, "
                    f"attempt {retry_count + 1}/{max_batch_retries}. "
                    f"Waiting {current_delay}s before retry..."
                )
                await asyncio.sleep(current_delay)

            # Process each failed text
            current_failed = list(failed_indices)
            new_failed_indices = set()
            had_rate_limit = False

            async def process_text(idx: int) -> None:
                try:
                    text_to_process = self._clean_text(texts[idx])
                    self.logger.debug(f"Processing text {idx + 1}/{len(texts)} - " f"Length: {len(text_to_process)}")

                    result = await loop.run_in_executor(
                        None,
                        partial(
                            genai.embed_content,
                            model="models/text-embedding-004",
                            content=text_to_process,
                            task_type=task_type,
                        ),
                    )

                    if not result or "embedding" not in result:
                        raise ProviderError(f"No embedding returned from model for text {idx + 1}")

                    embedding = list(result["embedding"])
                    self.logger.debug(f"Text {idx + 1}/{len(texts)} - Got embedding with {len(embedding)} dimensions")
                    results[idx] = embedding

                except exceptions.ResourceExhausted:
                    nonlocal had_rate_limit
                    had_rate_limit = True
                    self.logger.debug(f"Rate limit hit for text {idx + 1}, will retry after cooldown")
                    new_failed_indices.add(idx)
                except Exception as e:
                    self.logger.error(
                        f"Failed to get embeddings for text {idx + 1}/{len(texts)}: {str(e)}\n"
                        f"Text preview: {texts[idx][:100]}..."
                    )
                    # On non-rate-limit errors, return zero vector
                    results[idx] = [0.0] * self.get_dimensions()

            # Process texts concurrently with progress bar
            loop = asyncio.get_event_loop()
            pbar = tqdm(
                total=len(current_failed),
                desc=f"Generating embeddings (attempt {retry_count + 1}/{max_batch_retries})",
            )

            async def process_with_progress(idx: int) -> None:
                await process_text(idx)
                pbar.update(1)

            try:
                tasks = [process_with_progress(idx) for idx in current_failed]
                await asyncio.gather(*tasks)
            finally:
                pbar.close()

            # Update failed indices for next iteration
            failed_indices = new_failed_indices
            retry_count += 1

            # Adjust delay based on whether we hit rate limits
            if had_rate_limit:
                # If we're still hitting rate limits, increase delay
                current_delay = min(current_delay * 1.5, 120.0)  # Cap at 2 minutes
            elif current_delay > base_batch_delay:
                # If successful, gradually reduce delay but don't go below base
                current_delay = max(current_delay * 0.8, base_batch_delay)

        # Handle any remaining failed texts
        if failed_indices:
            self.logger.warning(
                f"Failed to get embeddings for {len(failed_indices)} texts after {max_batch_retries} attempts. "
                "Using zero vectors as fallback."
            )
            dims = self.get_dimensions()
            for idx in failed_indices:
                results[idx] = [0.0] * dims

        # Return results in original order
        return [results[i] for i in range(len(texts))]

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
