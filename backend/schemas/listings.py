"""Schema for product listings."""

import logging
from decimal import Decimal
from enum import Enum
from typing import Annotated, List, Optional

from beanie import Document, Indexed
from pydantic import BaseModel, HttpUrl, field_validator

from ..utils.utils import _to_decimal

logger = logging.getLogger(__name__)


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class OriginalId(BaseModel):
    """Schema for original IDs."""

    original_id: str
    site: str


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
    link: HttpUrl
    price_str: str  # Original price string
    price_value: Annotated[Optional[Decimal], Indexed()]  # Normalized price value

    # Photos
    photo_urls: List[HttpUrl] = []

    # Details (populated when fetching full listing)
    description: Optional[str]

    # Status flags
    more: bool = True  # Whether there are more details to fetch
    analysis_status: Annotated[AnalysisStatus, Indexed()] = AnalysisStatus.PENDING
    analysis_error: Optional[str] = None
    retry_count: Annotated[int, Indexed()] = 0

    # Compound index for analysis status and retry count
    analysis_status_retry_count: Annotated[None, Indexed()] = None

    # Add compound index for common analytics queries
    analysis_status_price: Annotated[None, Indexed()] = None
    site_timestamp: Annotated[None, Indexed()] = None

    @field_validator("price_value", mode="before")
    @classmethod
    def _to_decimal(cls, v):
        if isinstance(v, Decimal):
            return v
        if v is None:
            return None
        return _to_decimal(v)

    class Settings:
        name = "listings"
        indexes = [
            [("analysis_status", 1), ("price_value", 1)],  # For status/price correlation
            [("site", 1), ("timestamp", -1)],  # For marketplace trends
        ]


async def save_listings(listings: List[ListingDocument]) -> None:
    """Save listings to the database. Only deletes existing listings if they have identical content."""
    # Deduplicate incoming listings by original_id
    dedup_listings = {listing.original_id: listing for listing in listings}
    listings = list(dedup_listings.values())
    original_ids = [listing.original_id for listing in listings]

    # Get existing listings with the same original_ids
    existing_listings = await ListingDocument.find_many({"original_id": {"$in": original_ids}}).to_list()
    existing_by_id = {listing.original_id: listing for listing in existing_listings}

    # Separate listings into updates and new inserts
    to_delete_ids = []
    to_insert = []

    for listing in listings:
        existing = existing_by_id.get(listing.original_id)
        if existing:
            # Compare all fields except metadata fields
            new_dict = listing.model_dump(exclude={"id", "created_at", "updated_at"})
            existing_dict = existing.model_dump(exclude={"id", "created_at", "updated_at"})

            if new_dict != existing_dict:
                # Content is different, mark old for deletion and new for insertion
                to_delete_ids.append(listing.original_id)
                to_insert.append(listing)
        else:
            # No existing listing, just insert
            to_insert.append(listing)

    # Delete listings that have changed
    if to_delete_ids:
        await ListingDocument.find_many({"original_id": {"$in": to_delete_ids}}).delete_many()
        logger.info(f"Deleted {len(to_delete_ids)} changed listings")
        [logger.debug(f"Deleted changed listing {id}") for id in to_delete_ids]

    # Insert new and changed listings
    if to_insert:
        await ListingDocument.insert_many(to_insert)
        logger.info(f"Saved {len(to_insert)} new/changed listings")
        [logger.debug(f"Saved {listing.original_id}") for listing in to_insert]
    else:
        logger.info("No new or changed listings to save")
