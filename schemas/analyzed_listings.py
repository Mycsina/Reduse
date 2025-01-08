"""Schema for analyzed listings."""

from typing import Dict, Any
from beanie import Document


class AnalyzedListingDocument(Document):
    """Schema for analyzed listings.

    This schema stores the results of product analysis, including:
    1. Core product identification (brand, model, variant)
    2. Additional product information (specs, condition, etc.)
    3. Analysis metadata (version, retry count)
    """

    # Reference to original listing
    original_listing_id: str

    # Core product identification
    brand: str | None = None  # Manufacturer/company name
    model: str | None = None  # Product line/name
    variant: str | None = None  # Specific configuration/trim

    # Additional product information
    info: Dict[str, Any] = {}  # Flexible storage for additional details like:
    # - condition
    # - specifications
    # - features
    # - included items
    # - color
    # - warranty info
    # - etc.

    # Analysis metadata
    analysis_version: str  # Version of the analysis prompt/model used
    retry_count: int = 0  # Number of failed analysis attempts

    class Settings:
        name = "analyzed_listings"
        indexes = [
            "original_listing_id",
            "retry_count",
            "brand",  # Add indexes for common queries
            "model",
        ]
