"""Schema for analyzed listings."""

from typing import Annotated, Dict, Any, List
from beanie import Document, Indexed
from pymongo import GEOSPHERE


class AnalyzedListingDocument(Document):
    """Schema for analyzed listings.

    This schema stores the results of product analysis, including:
    1. Core product identification (brand, model, variant)
    2. Additional product information (specs, condition, etc.)
    3. Analysis metadata (version, retry count)
    4. Vector embeddings for similarity search
    """

    # Reference to original listing
    original_listing_id: Annotated[str, Indexed(unique=True)]

    # Core product identification
    brand: Annotated[str | None, Indexed()] = None  # Manufacturer/company name
    model: Annotated[str | None, Indexed()] = None  # Product line/name
    variant: str | None = None  # Specific configuration/trim

    # Additional product information
    info: Dict[str, Any] = {}  # Flexible storage for additional details

    # Vector embeddings for similarity search
    embeddings: Annotated[List[float] | None, Indexed(index_type=GEOSPHERE)] = None  # type: ignore # noqa: E501

    # Analysis metadata
    analysis_version: str  # Version of the analysis prompt/model used
    retry_count: Annotated[int, Indexed()] = 0  # Number of failed analysis attempts

    class Settings:
        name = "analyzed_listings"
