"""Composite AI provider implementation."""

import logging
from typing import Any, Dict, List, Optional, Union

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

    async def generate_text(
        self,
        prompt: str,
        temperature: float = 0.5,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text using Groq."""
        self.logger.debug(
            f"Generating text with Groq [model={self.groq.model}, temperature={temperature}, max_tokens={max_tokens}]"
        )
        result = await self.groq.generate_text(prompt, temperature, max_tokens)
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
        self.logger.debug(f"Processing batch with Groq [requests={len(requests)}, model={model}]")
        # Call process_batch dynamically since it might not exist
        results = await getattr(self.groq, "process_batch")(requests, model)
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        self.logger.debug(f"Batch processing complete [success={success_count}/{len(requests)}]")
        return results

    async def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """Get the status of a batch job using Groq."""
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