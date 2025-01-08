"""Schema for product listings."""

from decimal import Decimal, InvalidOperation
from typing import Optional
from bson import Decimal128
from pydantic import HttpUrl, validator, field_validator
from beanie import Document
from enum import Enum


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
    original_id: str
    site: str  # 'olx' or external site name
    title: str
    link: HttpUrl
    price_str: str  # Original price string
    price_value: Optional[Decimal] = None  # Normalized price value
    photo_url: Optional[HttpUrl] = None

    # Details (populated when fetching full listing)
    description: Optional[str] = None
    location: Optional[str] = None

    # Status flags
    more: bool = True  # Whether there are more details to fetch
    analysis_status: AnalysisStatus = AnalysisStatus.PENDING
    analysis_error: Optional[str] = None
    retry_count: int = 0

    @field_validator("price_value", mode="before")
    def parse_price(cls, v, values):
        """Parse price string to Decimal if not already set."""
        if v is None and "price_str" in values:
            try:
                # Remove currency symbols and normalize
                price_str = values["price_str"].replace("€", "").replace(".", "").replace(",", ".") # type: ignore
                # Extract first number found (ignore ranges)
                import re

                match = re.search(r"\d+\.?\d*", price_str)
                if match:
                    return Decimal(match.group())
            except (ValueError, InvalidOperation):
                pass
        return v
    
    @validator('price_value', pre=True)
    def convert_decimal128(cls, v):
        if isinstance(v, Decimal128):
            return v.to_decimal()
        return v

    class Settings:
        name = "listings"
        indexes = [
            "original_id",
            "site",
            "analysis_status",
            [("price_value", 1)],  # Index for price-based queries
            [("analysis_status", 1), ("retry_count", 1)],  # Index for retry queries
        ]
