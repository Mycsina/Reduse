"""Batch processing system for AI providers."""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from beanie import Document
from pydantic import Field, BaseModel

logger = logging.getLogger(__name__)


class BatchRequestResult(BaseModel):
    """Result status for a single request in a batch."""

    success: bool = Field(description="Whether the request was successful")
    error: Optional[str] = Field(None, description="Error message if failed")


class BatchRequest(Document):
    """Represents a batch request in the database."""

    input_hash: str = Field(description="Hash of the input data for deduplication")
    custom_id: str = Field(description="Custom ID for tracking the request")
    provider: str = Field(description="AI provider (e.g., 'groq')")
    status: str = Field(description="Current status of the batch")
    request_count: int = Field(description="Number of requests in this batch")
    provider_batch_id: Optional[str] = Field(None, description="Provider's batch ID (temporary)")
    provider_file_id: Optional[str] = Field(None, description="Provider's file ID (temporary)")
    result_status: Dict[str, BatchRequestResult] = Field(
        default_factory=dict,
        description="Status of each request by index",
    )
    error: Optional[str] = Field(None, description="Batch-level error message if failed")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(None)

    class Settings:
        name = "batch_requests"
        indexes = [
            "input_hash",
            "custom_id",
            "provider",
            "status",
            "provider_batch_id",
            [("provider", 1), ("status", 1)],
        ]


class BatchProcessor:
    """Base class for batch processing."""

    def __init__(self, provider: str):
        """Initialize the batch processor.

        Args:
            provider: Name of the AI provider
        """
        self.provider = provider
        self.logger = logger

    def _generate_hash(self, data: Dict[str, Any]) -> str:
        """Generate a deterministic hash for input data."""
        # Sort the dictionary to ensure consistent hashing
        sorted_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(sorted_str.encode()).hexdigest()

    def _generate_custom_id(self, prefix: str) -> str:
        """Generate a unique custom ID for tracking."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        return f"{prefix}-{timestamp}"

    async def create_batch(self, requests: List[Dict[str, Any]], prefix: str = "batch") -> BatchRequest:
        """Create a new batch request.

        Args:
            requests: List of request data to process
            prefix: Prefix for the custom ID

        Returns:
            Created BatchRequest document
        """
        input_hash = self._generate_hash({"requests": requests})
        custom_id = self._generate_custom_id(prefix)

        # Check for existing batch with same input
        existing = await BatchRequest.find_one({"input_hash": input_hash})
        if existing:
            self.logger.info(f"Found existing batch request with hash {input_hash}")
            return existing

        batch = BatchRequest(
            input_hash=input_hash,
            custom_id=custom_id,
            provider=self.provider,
            status="created",
            request_count=len(requests),
            provider_batch_id="",
            provider_file_id="",
            error=None,
            completed_at=None,
            result_status={},
        )
        await batch.insert()
        self.logger.info(f"Created new batch request {custom_id} with hash {input_hash}")
        return batch

    async def get_batch(self, custom_id: str) -> Optional[BatchRequest]:
        """Get a batch request by its custom ID."""
        return await BatchRequest.find_one({"custom_id": custom_id})

    async def get_batch_by_hash(self, input_hash: str) -> Optional[BatchRequest]:
        """Get a batch request by its input hash."""
        return await BatchRequest.find_one({"input_hash": input_hash})

    async def update_batch_status(
        self,
        batch: BatchRequest,
        status: str,
        error: Optional[str] = None,
        provider_ids: Optional[Dict[str, str]] = None,
    ) -> None:
        """Update batch status and related fields.

        Args:
            batch: Batch request to update
            status: New status
            error: Optional error message
            provider_ids: Optional provider IDs to update
        """
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow(),
        }

        if error:
            update_data["error"] = error

        if provider_ids:
            update_data.update(provider_ids)

        if status in ["completed", "failed", "cancelled"]:
            update_data["completed_at"] = datetime.utcnow()
            # Clear provider IDs as they're no longer needed
            update_data["provider_batch_id"] = None
            update_data["provider_file_id"] = None

        await batch.set(update_data)

    async def update_request_status(
        self,
        batch: BatchRequest,
        request_idx: int,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Update status for a single request in the batch.

        Args:
            batch: Batch request to update
            request_idx: Index of the request
            success: Whether the request was successful
            error: Optional error message
        """
        result = BatchRequestResult(success=success, error=error)
        batch.result_status[str(request_idx)] = result
        await batch.save()

    async def process_batch(self, batch: BatchRequest) -> BatchRequest:
        """Process a batch request. To be implemented by provider-specific classes."""
        raise NotImplementedError("Subclasses must implement process_batch")

    async def check_batch_status(self, batch: BatchRequest) -> BatchRequest:
        """Check the status of a batch request. To be implemented by provider-specific classes."""
        raise NotImplementedError("Subclasses must implement check_batch_status")

    async def get_batch_results(self, batch: BatchRequest) -> BatchRequest:
        """Get the results of a completed batch. To be implemented by provider-specific classes."""
        raise NotImplementedError("Subclasses must implement get_batch_results")
