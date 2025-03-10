"""Query service for listings and analyzed listings."""

import logging
import re
from decimal import Decimal, DecimalException
from typing import Any, Dict, List, Optional, Tuple

from beanie import PydanticObjectId
from beanie.operators import Or, RegEx

from ..schemas.analysis import AnalyzedListingDocument
from ..schemas.filtering import FilterCondition, FilterGroup, FilterGroupType
from ..schemas.listings import AnalysisStatus, ListingDocument

logger = logging.getLogger(__name__)


def build_mongo_query(filter_group: Optional[FilterGroup]) -> Dict[str, Any]:
    """Convert filter group to MongoDB query.

    Handles special field types:
    - price: Converted to Decimal for proper monetary value handling
    - text fields: Case-insensitive regex with proper escaping
    - numeric fields: Direct comparison
    - dates: ISO format
    """
    if not filter_group:
        return {}

    conditions = []
    for condition in filter_group.conditions:
        if isinstance(condition, FilterCondition):
            field = condition.field
            pattern = condition.pattern

            # Handle special fields
            if field == "price_value":
                try:
                    value = Decimal(pattern)
                    conditions.append({field: value})
                except (ValueError, DecimalException):
                    logger.warning(f"Invalid price value: {pattern}")
                    continue

            # Handle analyzed fields
            elif field in ["type", "brand", "base_model", "model_variant"]:
                conditions.append(
                    {field: {"$regex": re.escape(pattern), "$options": "i"}}
                )

            # Handle info fields
            else:
                conditions.append(
                    {f"info.{field}": {"$regex": re.escape(pattern), "$options": "i"}}
                )
        else:
            nested_query = build_mongo_query(condition)
            if nested_query:
                conditions.append(nested_query)

    if not conditions:
        return {}

    operator = "$and" if filter_group.type == FilterGroupType.AND else "$or"
    return {operator: conditions}


async def get_listings_data(
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
        logger.debug(f"Adding min price filter: {price_min}")
        filters.append({"price_value": {"$gte": price_min}})
    if price_max is not None:
        logger.debug(f"Adding max price filter: {price_max}")
        filters.append({"price_value": {"$lte": price_max}})
    if status:
        logger.debug(f"Adding status filter: {status}")
        filters.append(ListingDocument.analysis_status == status)
    if site:
        logger.debug(f"Adding site filter: {site}")
        filters.append(ListingDocument.site == site)
    if search_text:
        logger.debug(f"Adding text search filter: {search_text}")
        text_filter = Or(
            RegEx(ListingDocument.title, f".*{search_text}.*", "i"),
            RegEx(ListingDocument.description, f".*{search_text}.*", "i"),
        )
        filters.append(text_filter)

    # Ensure we only get listings with valid prices when filtering by price
    if price_min is not None or price_max is not None:
        filters.append({"price_value": {"$exists": True, "$ne": None}})

    query = {"$and": filters} if filters else {}
    logger.debug(f"Final query: {query}")
    return await ListingDocument.find(query).skip(skip).limit(limit).to_list()


async def get_listing_data(listing_id: str) -> Optional[ListingDocument]:
    """Get a specific listing by ID."""
    return await ListingDocument.get(PydanticObjectId(listing_id))


async def get_listing_by_original_id_data(
    original_id: str,
) -> Optional[ListingDocument]:
    """Get a specific listing by original ID."""
    return await ListingDocument.find_one({"original_id": original_id})


async def get_analyses_by_original_ids_data(
    original_ids: List[str],
) -> List[AnalyzedListingDocument]:
    """Get multiple analyses by original IDs in a single query."""
    return await AnalyzedListingDocument.find(
        {"original_listing_id": {"$in": original_ids}}
    ).to_list()


async def get_analyzed_listings_data(
    brand: Optional[str] = None,
    base_model: Optional[str] = None,
    variant: Optional[str] = None,
    original_id: List[str] = [],
    skip: int = 0,
    limit: int = 12,
) -> List[Tuple[ListingDocument, AnalyzedListingDocument]]:
    """Get analyzed listings with optional filters and their original listings."""
    filters = []

    if brand:
        filters.append(RegEx(AnalyzedListingDocument.brand, f".*{brand}.*", "i"))
    if base_model:
        filters.append(
            RegEx(AnalyzedListingDocument.base_model, f".*{base_model}.*", "i")
        )
    if variant:
        filters.append(
            RegEx(AnalyzedListingDocument.model_variant, f".*{variant}.*", "i")
        )
    if original_id:
        filters.append({"original_listing_id": {"$in": original_id}})

    query = {"$and": filters} if filters else {}

    analyzed_listings = (
        await AnalyzedListingDocument.find(query).skip(skip).limit(limit).to_list()
    )
    ids = [analyzed.original_listing_id for analyzed in analyzed_listings]
    listings = await ListingDocument.find({"original_id": {"$in": ids}}).to_list()

    return list(zip(listings, analyzed_listings))


async def get_analyzed_listing_data(
    analyzed_id: str,
) -> Optional[Tuple[ListingDocument, AnalyzedListingDocument]]:
    """Get a specific analysis by ID with its listing."""
    analyzed = await AnalyzedListingDocument.get(PydanticObjectId(analyzed_id))
    if not analyzed:
        return None

    original = await ListingDocument.find_one(
        {"original_id": analyzed.original_listing_id}
    )
    if not original:
        return None

    return (original, analyzed)


async def get_analysis_by_original_id_data(
    original_id: str,
) -> Optional[AnalyzedListingDocument]:
    """Get a specific analysis by original ID."""
    return await AnalyzedListingDocument.find_one({"original_listing_id": original_id})


async def get_similar_listings_data(
    listing_id: str, limit: int = 6, offset: int = 0
) -> List[ListingDocument]:
    """Get similar listings based on embeddings similarity."""
    listing = await ListingDocument.get(listing_id)
    if not listing or not listing.analysis_status == AnalysisStatus.COMPLETED:
        return []

    logger.debug(f"Finding similar listings for: {listing.original_id}")

    analysis = await get_analysis_by_original_id_data(listing.original_id)
    if not analysis or not analysis.embeddings:
        return []

    logger.debug(
        f"Found analysis with embeddings: {analysis.model_dump_json(exclude={'embeddings'})}"
    )  # exclude embeddings

    # Use MongoDB's $nearSphere operator for vector similarity search
    # Only use listings with the same type
    similar_query = {
        "type": analysis.type,
        "embeddings": {
            "$nearSphere": {
                "$geometry": {"type": "Point", "coordinates": analysis.embeddings}
            }
        },
        "original_listing_id": {
            "$ne": listing.original_id
        },  # Exclude the query listing
    }

    logger.debug(f"Searching for similar listings of type: {analysis.type}")

    # Get similar analyzed listings with offset
    similar_analyzed = (
        await AnalyzedListingDocument.find(similar_query)
        .skip(offset)
        .limit(limit)
        .to_list()
    )
    logger.debug(
        f"Found {len(similar_analyzed)} similar listings of type {analysis.type} (offset: {offset}, limit: {limit})"
    )

    # Get original listings for the similar analyzed listings
    original_ids = [analyzed.original_listing_id for analyzed in similar_analyzed]
    similar_listings = await ListingDocument.find(
        {"original_id": {"$in": original_ids}}
    ).to_list()

    return similar_listings


async def get_listings_with_analysis_data(
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    search_text: Optional[str] = None,
    filter_group: Optional[FilterGroup] = None,
    skip: int = 0,
    limit: int = 12,
) -> List[Tuple[ListingDocument, Optional[AnalyzedListingDocument]]]:
    """Get listings with optional filters and analysis data."""
    # Start building the pipeline
    pipeline = []

    # First stage: Join with analyzed_listings
    pipeline.append(
        {
            "$lookup": {
                "from": "analyzed_listings",
                "localField": "original_id",
                "foreignField": "original_listing_id",
                "as": "analysis",
            }
        }
    )

    # Unwind the analysis array (with preserveNullAndEmptyArrays to keep listings without analysis)
    pipeline.append(
        {"$unwind": {"path": "$analysis", "preserveNullAndEmptyArrays": True}}
    )

    # Build match conditions
    match_conditions = []

    # Handle price filters
    if price_min is not None or price_max is not None:
        price_query = {}
        if price_min is not None:
            price_query["$gte"] = Decimal(str(price_min))
        if price_max is not None:
            price_query["$lte"] = Decimal(str(price_max))
        if price_query:
            match_conditions.append({"price_value": price_query})

    # Handle text search
    if search_text:
        match_conditions.append(
            {
                "$or": [
                    {"title": {"$regex": search_text, "$options": "i"}},
                    {"description": {"$regex": search_text, "$options": "i"}},
                ]
            }
        )

    # Handle advanced filter group (which may include analysis fields)
    if filter_group:
        advanced_filter = build_mongo_query(filter_group)
        if advanced_filter:
            # Transform field references to include analysis prefix where needed
            def transform_filter(
                query: Dict[str, Any] | List[Any],
            ) -> Dict[str, Any] | List[Any]:
                if isinstance(query, list):
                    return [transform_filter(item) for item in query]
                if not isinstance(query, dict):
                    return query
                transformed = {}
                logger.debug(f"Transforming filter: {query}")
                for k, v in query.items():
                    logger.debug(f"Transforming filter: {k} = {v}")
                    if k in ["type", "brand", "base_model", "model_variant"]:
                        transformed[f"analysis.{k}"] = transform_filter(v)
                    elif k.startswith("info."):
                        transformed[f"analysis.{k}"] = transform_filter(v)
                    else:
                        transformed[k] = transform_filter(v)
                return transformed

            match_conditions.append(transform_filter(advanced_filter))

    # Add match stage if we have conditions
    if match_conditions:
        pipeline.append(
            {
                "$match": (
                    {"$and": match_conditions}
                    if len(match_conditions) > 1
                    else match_conditions[0]
                )
            }
        )

    # Add pagination
    pipeline.extend([{"$skip": skip}, {"$limit": limit}])

    logger.debug(f"Pipeline: {pipeline}")
    # Execute pipeline and convert results to Pydantic models
    results = await ListingDocument.aggregate(pipeline).to_list()

    listings_with_analysis = []
    for result in results:
        logger.debug(f"Result: {result['title']}")
        listing = ListingDocument.model_validate(result)
        analysis = (
            AnalyzedListingDocument.model_validate(result["analysis"])
            if result.get("analysis")
            else None
        )
        listings_with_analysis.append((listing, analysis))

    logger.debug(f"Returned {len(listings_with_analysis)} listings with analysis")
    return listings_with_analysis


async def get_distinct_info_fields_data() -> List[str]:
    """Get all distinct fields used in the info dictionary across all analyzed listings."""
    pipeline = [
        {"$project": {"info_fields": {"$objectToArray": "$info"}}},
        {"$unwind": "$info_fields"},
        {"$group": {"_id": "$info_fields.k"}},
        {"$sort": {"_id": 1}},
    ]

    result = await AnalyzedListingDocument.aggregate(pipeline).to_list()
    return [doc["_id"] for doc in result]


async def get_similar_listings_with_analysis_data(
    listing_id: str, skip: int = 0, limit: int = 12
) -> List[Tuple[ListingDocument, Optional[AnalyzedListingDocument]]]:
    """Get similar listings with their analysis data."""
    similar = await get_similar_listings_data(listing_id, limit, skip)
    if not similar:
        return []

    # Get analysis data for similar listings
    original_ids = [listing.original_id for listing in similar]
    return await query_listings_with_analysis_raw(
        {"original_id": {"$in": original_ids}}, skip=0, limit=len(original_ids)
    )


async def query_listings_with_analysis_raw(
    query: Dict[str, Any],
    skip: int = 0,
    limit: int = 12,
) -> List[Tuple[ListingDocument, Optional[AnalyzedListingDocument]]]:
    """Query listings with analyzed fields using a raw MongoDB query."""
    # Start with the lookup pipeline to join collections
    pipeline = [
        {
            "$lookup": {
                "from": "analyzed_listings",
                "localField": "original_id",
                "foreignField": "original_listing_id",
                "as": "analysis",
            }
        },
        # Unwind analysis array while preserving listings without analysis
        {"$unwind": {"path": "$analysis", "preserveNullAndEmptyArrays": True}},
        # Apply the raw query
        {"$match": query},
        # Add pagination
        {"$skip": skip},
        {"$limit": limit},
    ]

    # Execute pipeline and convert results to Pydantic models
    results = await ListingDocument.aggregate(pipeline).to_list()

    listings_with_analysis = []
    for result in results:
        listing = ListingDocument.model_validate(result)
        analysis = (
            AnalyzedListingDocument.model_validate(result["analysis"])
            if result.get("analysis")
            else None
        )
        listings_with_analysis.append((listing, analysis))

    return listings_with_analysis


async def get_listing_with_analysis_data(
    listing_id: str,
) -> Optional[Tuple[ListingDocument, Optional[AnalyzedListingDocument]]]:
    """Get a specific listing with its analysis data."""
    listing = await ListingDocument.get(PydanticObjectId(listing_id))
    if not listing:
        return None

    analysis = await get_analysis_by_original_id_data(listing.original_id)
    return (listing, analysis)
