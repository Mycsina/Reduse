"""Query logic for listings and analyzed listings."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from beanie import PydanticObjectId
from beanie.operators import Or, RegEx

from ..schemas.analyzed_listings import AnalyzedListingDocument
from ..schemas.listings import AnalysisStatus, ListingDocument

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
    filters = []

    if price_min is not None:
        filters.append({"price_value": {"$gte": price_min}})
    if price_max is not None:
        filters.append({"price_value": {"$lte": price_max}})
    if status:
        filters.append(ListingDocument.analysis_status == status)
    if site:
        filters.append(ListingDocument.site == site)
    if search_text:
        text_filter = Or(
            RegEx(ListingDocument.title, f".*{search_text}.*", "i"),
            RegEx(ListingDocument.description, f".*{search_text}.*", "i"),
        )
        filters.append(text_filter)

    query = {"$and": filters} if filters else {}
    logger.info(f"Query: {query}")
    return await ListingDocument.find(query).skip(skip).limit(limit).to_list()


async def get_listing(listing_id: str) -> Optional[ListingDocument]:
    """Get a specific listing by ID."""
    return await ListingDocument.get(PydanticObjectId(listing_id))


async def get_listing_by_original_id(original_id: str) -> Optional[ListingDocument]:
    """Get a specific listing by original ID."""
    return await ListingDocument.find_one({"original_id": original_id})


async def get_analyzed_listings(
    brand: Optional[str] = None,
    model: Optional[str] = None,
    original_id: List[str] = [],
    skip: int = 0,
    limit: int = 12,
) -> List[Tuple[ListingDocument, AnalyzedListingDocument]]:
    """Get analyzed listings with optional filters and their original listings."""
    filters = []

    if brand:
        filters.append(RegEx(AnalyzedListingDocument.brand, f".*{brand}.*", "i"))
    if model:
        filters.append(RegEx(AnalyzedListingDocument.model, f".*{model}.*", "i"))
    if original_id:
        filters.append({"original_listing_id": {"$in": original_id}})

    query = {"$and": filters} if filters else {}

    analyzed_listings = await AnalyzedListingDocument.find(query).skip(skip).limit(limit).to_list()
    ids = [analyzed.original_listing_id for analyzed in analyzed_listings]
    listings = await ListingDocument.find({"original_id": {"$in": ids}}).to_list()

    return list(zip(listings, analyzed_listings))


async def get_analyzed_listing(analyzed_id: str) -> Optional[Tuple[ListingDocument, AnalyzedListingDocument]]:
    """Get a specific analysis by ID with its listing."""
    analyzed = await AnalyzedListingDocument.get(PydanticObjectId(analyzed_id))
    if not analyzed:
        return None

    original = await ListingDocument.find_one({"original_id": analyzed.original_listing_id})
    if not original:
        return None

    return (original, analyzed)


async def get_analysis_by_original_id(original_id: str) -> Optional[AnalyzedListingDocument]:
    """Get a specific analysis by original ID."""
    return await AnalyzedListingDocument.find_one({"original_listing_id": original_id})


async def get_similar_listings(listing_id: str, limit: int = 6) -> List[ListingDocument]:
    """Get similar listings based on embeddings similarity."""
    listing = await ListingDocument.get(listing_id)
    if not listing or not listing.analysis_status == AnalysisStatus.COMPLETED:
        return []

    logger.info(f"Finding similar listings for: {listing}")

    analysis = await get_analysis_by_original_id(listing.original_id)
    if not analysis or not analysis.embeddings:
        return []

    logger.info(f"Found analysis with embeddings: {analysis}")

    # Use MongoDB's $nearSphere operator for vector similarity search
    similar_query = {
        "embeddings": {"$nearSphere": {"$geometry": {"type": "Point", "coordinates": analysis.embeddings}}},
        "original_listing_id": {"$ne": listing.original_id},  # Exclude the query listing
    }

    logger.info(f"Similar query: {similar_query}")

    # Get similar analyzed listings
    similar_analyzed = await AnalyzedListingDocument.find(similar_query).limit(limit).to_list()

    # Get original listings for the similar analyzed listings
    original_ids = [analyzed.original_listing_id for analyzed in similar_analyzed]
    similar_listings = await ListingDocument.find({"original_id": {"$in": original_ids}}).to_list()

    return similar_listings


async def query_analyzed_listings_raw(query: Dict[str, Any]) -> List[Tuple[ListingDocument, AnalyzedListingDocument]]:
    """Query analyzed listings using a raw MongoDB query and get their original listings."""
    analyzed_listings = await AnalyzedListingDocument.find(query).to_list()

    result = []
    for analyzed in analyzed_listings:
        original = await ListingDocument.find_one({"original_id": analyzed.original_listing_id})
        if original:
            result.append((original, analyzed))

    return result
