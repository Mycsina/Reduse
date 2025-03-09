"""Batch processing schemas."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from beanie import Document
from bson import ObjectId
from pydantic import BaseModel, Field


class BatchStatus(str, Enum):
    """Status of a batch job."""

    CREATED = "created"
    UPLOADING = "uploading"
    VALIDATING = "validating"
    IN_PROGRESS = "in_progress"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"


class BatchRequestResult(BaseModel):
    """Result status for a single request in a batch."""

    success: bool = Field(description="Whether the request was successful")
    error: Optional[str] = Field(None, description="Error message if failed")


class BatchJobDocument(Document):
    """Document for tracking batch jobs."""

    batch_id: str = Field(description="Provider's batch ID")
    status: BatchStatus = Field(description="Current status of the batch")
    listings: List[ObjectId] = Field(description="List of listing IDs in this batch")
    request_count: int = Field(description="Number of requests in this batch")
    result_status: Dict[str, BatchRequestResult] = Field(
        default_factory=dict,
        description="Status of each request by index",
    )
    error: Optional[str] = Field(
        None, description="Batch-level error message if failed"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(None)
    completed_at: Optional[datetime] = Field(None)
    cancelled_at: Optional[datetime] = Field(None)
    expires_at: Optional[datetime] = Field(None)

    class Settings:
        name = "batch_jobs"
        indexes = [
            "batch_id",
            "status",
            [
                ("status", 1),
                ("created_at", -1),
            ],  # For listing batches by status and age
        ]

    class Config:
        arbitrary_types_allowed = True  # Allow ObjectId
