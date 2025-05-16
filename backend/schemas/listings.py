"""Schema for product listings."""

import logging
from datetime import datetime
from enum import Enum
from typing import Annotated, List, Optional

from beanie import Document, Indexed
from pydantic import HttpUrl

logger = logging.getLogger(__name__)


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ListingDocument(Document):
    """Schema for product listings.

    This schema stores the raw listing data as scraped from various sources.
    Fields are populated in two stages:
    1. Basic info from listing cards (always populated)
    2. Details (description, location) from individual listing pages (optional)
    """

    # Basic info (always populated)
    original_id: Annotated[str, Indexed(unique=True)]
    site: Annotated[str, Indexed()]  # 'olx' or external site name
    title: str
    price_str: str  # Original price string
    price_value: Annotated[Optional[float], Indexed()]  # Normalized price value

    # Photos
    photo_urls: List[HttpUrl] = []

    # Details (populated when fetching full listing)
    description: Optional[str] = None
    parameters: Optional[dict[str, str]] = None
    link: Optional[HttpUrl] = None

    # Status flags
    more: bool = True  # Whether there are more details to fetch
    analysis_status: Annotated[AnalysisStatus, Indexed()] = AnalysisStatus.PENDING
    analysis_error: Optional[str] = None
    retry_count: Annotated[int, Indexed()] = 0
    timestamp: Annotated[datetime, Indexed()] = datetime.now()

    class Settings:
        name = "listings"
        indexes = [
            [
                ("analysis_status", 1),
                ("price_value", 1),
            ],  # For status/price correlation
            [("site", 1), ("timestamp", -1)],  # For marketplace trends
        ]
