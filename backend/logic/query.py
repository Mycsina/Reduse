"""Query logic for listings and analyzed listings."""

import logging
from typing import List, Optional, Tuple

from ..schemas.analysis import AnalyzedListingDocument
from ..schemas.listings import AnalysisStatus, ListingDocument
from ..schemas.query import FilterGroup
from ..services.query import (get_analyses_by_original_ids_data,
                              get_analysis_by_original_id_data,
                              get_analyzed_listing_data,
                              get_analyzed_listings_data,
                              get_distinct_info_fields_data,
                              get_listing_by_original_id_data,
                              get_listing_data, get_listing_with_analysis_data,
                              get_listings_data,
                              get_listings_with_analysis_data,
                              get_similar_listings_data,
                              get_similar_listings_with_analysis_data)

logger = logging.getLogger(__name__)


async def get_listings(
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    status: Optional[AnalysisStatus] = None,
    site: Optional[str] = None,
    search_text: Optional[str] = None,
    skip: int = 0,
    limit: int = 12,
) -> List[ListingDocument]:
    """Get listings with optional filters and pagination."""
    return await get_listings_data(
        price_min, price_max, status, site, search_text, skip, limit
    )


async def get_listing(listing_id: str) -> Optional[ListingDocument]:
    """Get a specific listing by ID."""
    return await get_listing_data(listing_id)


async def get_listing_by_original_id(original_id: str) -> Optional[ListingDocument]:
    """Get a specific listing by original ID."""
    return await get_listing_by_original_id_data(original_id)


async def get_analyses_by_original_ids(
    original_ids: List[str],
) -> List[AnalyzedListingDocument]:
    """Get multiple analyses by original IDs."""
    return await get_analyses_by_original_ids_data(original_ids)


async def get_analyzed_listings(
    brand: Optional[str] = None,
    base_model: Optional[str] = None,
    variant: Optional[str] = None,
    original_id: List[str] = [],
    skip: int = 0,
    limit: int = 12,
) -> List[Tuple[ListingDocument, AnalyzedListingDocument]]:
    """Get analyzed listings with optional filters."""
    return await get_analyzed_listings_data(
        brand, base_model, variant, original_id, skip, limit
    )


async def get_analyzed_listing(
    analyzed_id: str,
) -> Optional[Tuple[ListingDocument, AnalyzedListingDocument]]:
    """Get a specific analysis by ID with its listing."""
    return await get_analyzed_listing_data(analyzed_id)


async def get_analysis_by_original_id(
    original_id: str,
) -> Optional[AnalyzedListingDocument]:
    """Get a specific analysis by original ID."""
    return await get_analysis_by_original_id_data(original_id)


async def get_similar_listings(
    listing_id: str, limit: int = 6, offset: int = 0
) -> List[ListingDocument]:
    """Get similar listings based on embeddings similarity."""
    return await get_similar_listings_data(listing_id, limit, offset)


async def get_listings_with_analysis(
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    search_text: Optional[str] = None,
    filter_group: Optional[FilterGroup] = None,
    skip: int = 0,
    limit: int = 12,
) -> List[Tuple[ListingDocument, Optional[AnalyzedListingDocument]]]:
    """Get listings with optional filters and analysis data."""
    return await get_listings_with_analysis_data(
        price_min, price_max, search_text, filter_group, skip, limit
    )


async def get_distinct_info_fields() -> List[str]:
    """Get all distinct fields used in the info dictionary."""
    return await get_distinct_info_fields_data()


async def get_similar_listings_with_analysis(
    listing_id: str, skip: int = 0, limit: int = 12
) -> List[Tuple[ListingDocument, Optional[AnalyzedListingDocument]]]:
    """Get similar listings with their analysis data."""
    return await get_similar_listings_with_analysis_data(listing_id, skip, limit)


async def get_listing_with_analysis(
    listing_id: str,
) -> Optional[Tuple[ListingDocument, Optional[AnalyzedListingDocument]]]:
    """Get a specific listing with its analysis data."""
    return await get_listing_with_analysis_data(listing_id)
