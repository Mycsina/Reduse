"""Schema for bug reports."""

import logging
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BugReportStatus(str, Enum):
    """Status of a bug report."""

    OPEN = "open"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"
    INVALID = "invalid"


class BugReportType(str, Enum):
    """Type of bug report."""

    INCORRECT_DATA = "incorrect_data"
    MISSING_DATA = "missing_data"
    WRONG_ANALYSIS = "wrong_analysis"
    OTHER = "other"


class BugReportDocument(Document):
    """Schema for bug reports on listings.

    This schema stores user-submitted bug reports related to listings with
    incorrect or problematic data. These reports can be used to improve
    data quality and fine-tune models.
    """

    # Reference to the listing
    listing_id: Annotated[str, Indexed()]
    original_id: Annotated[str, Indexed()]
    site: Annotated[str, Indexed()]

    # Bug report details
    report_type: BugReportType
    description: str
    incorrect_fields: Optional[Dict[str, Any]] = None
    expected_values: Optional[Dict[str, Any]] = None

    # Metadata
    status: Annotated[BugReportStatus, Indexed()] = BugReportStatus.OPEN
    resolution_notes: Optional[str] = None
    timestamp: Annotated[datetime, Indexed()] = Field(default_factory=datetime.now)

    class Settings:
        name = "bug_reports"
        indexes = [
            [("listing_id", 1), ("timestamp", -1)],  # For listing-specific reports
            [("status", 1), ("timestamp", 1)],  # For processing open reports
            [("original_id", 1), ("site", 1)],  # Match listing uniqueness
        ]


class BugReportCreate(BaseModel):
    """Schema for creating a bug report."""

    listing_id: str
    original_id: str
    site: str
    report_type: BugReportType
    description: str
    incorrect_fields: Optional[Dict[str, Any]] = None
    expected_values: Optional[Dict[str, Any]] = None


class BugReportResponse(BaseModel):
    """Response schema for bug reports."""

    id: str
    listing_id: str
    report_type: BugReportType
    description: str
    status: BugReportStatus
    timestamp: datetime
