"""Composite AI provider implementation."""

import logging
from typing import Any, Callable, Dict, Iterator, List, Optional, Union

from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.llms import ChatMessage, CompletionResponse, CustomLLM, MessageRole

from ...config import settings
from ...schemas.batch import BatchStatus
from .base import BaseProvider
from .google import GoogleAIProvider
from .groq import GroqProvider


class CompositeProvider(BaseProvider):
    """Provider that combines multiple AI providers with LlamaIndex compatibility.

    Currently uses:
    - Groq for text generation and batch processing
    - Google for embeddings
    """

    def __init__(self):
        """Initialize the composite provider."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Initializing CompositeProvider")
        self.groq = GroqProvider(api_key=settings.ai.groq_api_key.get_secret_value())
        self.google = GoogleAIProvider()
        self._dimensions = self.google._dimensions  # Use Google's embedding dimensions
        # Check if the provider supports batch operations
        self.supports_batch = hasattr(self.groq, "process_batch")
        self.logger.debug(f"CompositeProvider initialized with batch support: {self.supports_batch}")

    async def generate_text(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.5,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text using Groq."""
        self.logger.debug(
            f"Generating text with Groq [model={model}, temperature={temperature}, max_tokens={max_tokens}]"
        )
        result = await self.groq.generate_text(prompt, model, temperature, max_tokens)
        self.logger.debug(f"Generated text length: {len(result)}")
        return result

    async def generate_json(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.5,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate JSON using Groq."""
        self.logger.debug(
            f"Generating JSON with Groq [model={model}, temperature={temperature}, max_tokens={max_tokens}]"
        )
        result = await self.groq.generate_json(prompt, model, temperature, max_tokens)
        self.logger.debug(f"Generated JSON with keys: {list(result.keys())}")
        return result

    async def process_batch(
        self,
        requests: List[Dict[str, Any]],
        model: Optional[str] = None,
    ) -> List[Union[Dict[str, Any], Exception]]:
        """Process a batch of requests using Groq."""
        if not self.supports_batch:
            raise NotImplementedError("Batch processing not supported by this provider")

        self.logger.debug(f"Processing batch with Groq [requests={len(requests)}, model={model}]")
        # Call process_batch dynamically since it might not exist
        results = await getattr(self.groq, "process_batch")(requests, model)
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        self.logger.debug(f"Batch processing complete [success={success_count}/{len(requests)}]")
        return results

    async def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """Get the status of a batch job using Groq."""
        if not self.supports_batch:
            raise NotImplementedError("Batch processing not supported by this provider")

        self.logger.debug(f"Getting batch status [batch_id={batch_id}]")
        # Call get_batch_status dynamically since it might not exist
        batch_doc = await getattr(self.groq, "get_batch_status")(batch_id)
        result = {
            "batch_id": batch_doc.batch_id,
            "status": batch_doc.status,
            "request_count": batch_doc.request_count,
            "result_status": {k: v.dict() for k, v in batch_doc.result_status.items()},
            "error": batch_doc.error,
            "created_at": batch_doc.created_at,
            "completed_at": batch_doc.completed_at,
        }
        self.logger.debug(
            f"Batch status retrieved [status={result['status']}, "
            f"requests={result['request_count']}, error={result['error']}]"
        )
        return result

    async def cancel_batch(self, batch_id: str) -> None:
        """Cancel a batch job using Groq."""
        if not self.supports_batch:
            raise NotImplementedError("Batch processing not supported by this provider")

        self.logger.debug(f"Cancelling batch [batch_id={batch_id}]")
        # Call cancel_batch dynamically since it might not exist
        await getattr(self.groq, "cancel_batch")(batch_id)
        self.logger.debug(f"Batch cancelled successfully [batch_id={batch_id}]")

    async def list_batches(
        self,
        status: Optional[BatchStatus] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """List batch jobs using Groq."""
        if not self.supports_batch:
            raise NotImplementedError("Batch processing not supported by this provider")

        self.logger.debug(f"Listing batches [status={status}, limit={limit}, skip={skip}]")
        # Call list_batches dynamically since it might not exist
        batch_docs = await getattr(self.groq, "list_batches")(status=status, limit=limit, skip=skip)
        results = [
            {
                "batch_id": doc.batch_id,
                "status": doc.status,
                "request_count": doc.request_count,
                "result_status": {k: v.dict() for k, v in doc.result_status.items()},
                "error": doc.error,
                "created_at": doc.created_at,
                "completed_at": doc.completed_at,
            }
            for doc in batch_docs
        ]
        self.logger.debug(f"Retrieved {len(results)} batch documents")
        return results

    async def get_embeddings(
        self,
        text: Union[str, List[str]],
        _: Any = None,  # Keep Google's task_type parameter but make it optional
        max_batch_retries: int = 5,
        base_batch_delay: float = 30.0,
    ) -> List[List[float]]:
        """Get embeddings using Google."""
        text_count = len(text) if isinstance(text, list) else 1
        self.logger.debug(
            f"Getting embeddings from Google [texts={text_count}, "
            f"max_retries={max_batch_retries}, base_delay={base_batch_delay}]"
        )
        embeddings = await self.google.get_embeddings(
            text,
            None,  # type: ignore
            max_batch_retries=max_batch_retries,
            base_batch_delay=base_batch_delay,
        )
        self.logger.debug(f"Generated {len(embeddings)} embeddings of dimension {len(embeddings[0])}")
        return embeddings

    def get_dimensions(self) -> int:
        """Get the dimensionality of the embeddings vectors."""
        dimensions = self.google.get_dimensions()
        self.logger.debug(f"Embedding dimensions: {dimensions}")
        return dimensions

    def as_llamaindex_llm(self) -> CustomLLM:
        """Get a LlamaIndex-compatible LLM.

        Returns:
            CustomLLM: LlamaIndex LLM interface
        """

        class CompositeProviderLLM(CustomLLM):
            def __init__(self, provider: CompositeProvider):
                super().__init__()
                self.provider = provider

            @property
            def metadata(self) -> Dict[str, Any]:
                """Get the metadata for this LLM."""
                return {
                    "model": settings.ai.default_model,
                    "type": "composite_provider",
                }

            @property
            def _llm_type(self) -> str:
                return "composite_provider"

            def complete(self, prompt: str, **kwargs: Any) -> str:
                """Synchronous completion not supported, must use async."""
                raise NotImplementedError("Synchronous completion not supported, use acomplete instead")

            def stream_complete(self, prompt: str, **kwargs: Any) -> Iterator[CompletionResponse]:
                """Synchronous streaming not supported, must use async version."""
                raise NotImplementedError("Synchronous streaming not supported")

            async def acomplete(self, prompt: str, **kwargs: Any) -> str:
                """Complete the prompt with the Groq provider."""
                model = kwargs.get("model", settings.ai.default_model)
                temperature = kwargs.get("temperature", 0.7)
                max_tokens = kwargs.get("max_tokens", None)
                return await self.provider.generate_text(prompt, model, temperature, max_tokens)

            async def achat(self, messages: List[ChatMessage], **kwargs: Any) -> str:
                """Process chat messages with the Groq provider."""
                # Convert LlamaIndex ChatMessage to text prompt
                system_message = next((m for m in messages if m.role == MessageRole.SYSTEM), None)

                # Format as a chat prompt
                formatted_prompt = ""
                if system_message:
                    formatted_prompt += f"System: {system_message.content}\n\n"

                for msg in messages:
                    if msg.role == MessageRole.SYSTEM:
                        continue
                    role_str = "User" if msg.role == MessageRole.USER else "Assistant"
                    formatted_prompt += f"{role_str}: {msg.content}\n"

                formatted_prompt += "Assistant: "

                model = kwargs.get("model", settings.ai.default_model)
                temperature = kwargs.get("temperature", 0.7)
                max_tokens = kwargs.get("max_tokens", None)

                return await self.provider.generate_text(formatted_prompt, model, temperature, max_tokens)

        return CompositeProviderLLM(self)

    def as_llamaindex_embedding(self) -> BaseEmbedding:
        """Get a LlamaIndex-compatible embedding model.

        Returns:
            BaseEmbedding: LlamaIndex embedding model
        """

        class CompositeProviderEmbedding(BaseEmbedding):
            def __init__(self, provider: CompositeProvider):
                super().__init__()
                self.provider = provider
                self._embed_batch_size = 50

            @property
            def embed_dim(self) -> int:
                return self.provider.get_dimensions()

            def _get_query_embedding(self, query: str) -> List[float]:
                """Synchronous query embedding not supported, must use async."""
                raise NotImplementedError("Synchronous embedding not supported, use async methods")

            def _get_text_embedding(self, text: str) -> List[float]:
                """Synchronous text embedding not supported, must use async."""
                raise NotImplementedError("Synchronous embedding not supported, use async methods")

            async def _aget_query_embedding(self, query: str) -> List[float]:
                embeddings = await self.provider.get_embeddings(query)
                return embeddings[0]

            async def _aget_text_embedding(self, text: str) -> List[float]:
                embeddings = await self.provider.get_embeddings(text)
                return embeddings[0]

            async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
                return await self.provider.get_embeddings(texts)

        return CompositeProviderEmbedding(self)
