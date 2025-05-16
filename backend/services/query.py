"""Query service for listings and analyzed listings."""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from beanie import PydanticObjectId
from beanie.operators import Or, RegEx

from backend.schemas.analysis import AnalyzedListingDocument
from backend.schemas.filtering import (FilterCondition, FilterGroup,
                                       FilterGroupType, Operator)
from backend.schemas.listings import AnalysisStatus, ListingDocument

logger = logging.getLogger(__name__)

# Cache configuration
PROTECTED_FIELDS = {"type", "brand", "base_model", "model_variant"}
MIN_OCCURRENCE_THRESHOLD = (
    5  # Minimum number of occurrences for a field to be considered common
)


# Helper function to attempt numeric conversion
def _try_convert_numeric(value: str) -> Optional[float | int]:
    try:
        # Attempt float conversion first
        if "." in value or "e" in value.lower():
            return float(value)
        # Otherwise, attempt integer conversion
        else:
            return int(value)
    except ValueError:
        # Return None if conversion fails for both float and int
        return None


def build_mongo_query(
    filter_group: Optional[FilterGroup], field_prefix: Optional[str] = None
) -> Dict[str, Any]:
    """Convert filter group to MongoDB query.

    Handles operators and attempts type conversion for numerical comparisons.
    The field_prefix (e.g., 'analysis.') is added when called from within the aggregation pipeline context.
    Correctly handles dynamic fields within analysis.info.
    """
    if not filter_group:
        return {}

    conditions = []
    for condition in filter_group.conditions:
        if isinstance(condition, FilterCondition):
            field = condition.field
            operator = condition.operator
            value = condition.value
            mongo_field: str

            # Construct the correct MongoDB field path
            if field_prefix == "analysis":
                if field in PROTECTED_FIELDS:
                    mongo_field = f"analysis.{field}"
                else:
                    # Assume any other field in the analysis context is a dynamic info field
                    mongo_field = f"analysis.info.{field}"
            elif field == "price_value":  # Handle top-level price field
                mongo_field = "price_value"
            elif (
                field in PROTECTED_FIELDS
            ):  # Handle top-level analyzed fields (if query is not prefixed)
                mongo_field = field
            else:
                # Assume any other top-level field is an info field (less common scenario)
                mongo_field = f"info.{field}"

            # Handle different operators
            condition_query = None
            numeric_value = _try_convert_numeric(value)

            if operator == Operator.EQUALS:
                # Case-insensitive exact match for strings
                condition_query = {
                    mongo_field: {"$regex": f"^{re.escape(value)}$", "$options": "i"}
                }
            elif operator == Operator.CONTAINS:
                # Case-insensitive substring match
                condition_query = {
                    mongo_field: {"$regex": re.escape(value), "$options": "i"}
                }
            elif operator == Operator.REGEX:
                # Direct regex (user provides the pattern)
                try:
                    # Validate regex - basic check
                    re.compile(value)
                    condition_query = {
                        mongo_field: {"$regex": value, "$options": "i"}
                    }  # Assume case-insensitive for now
                except re.error as e:
                    logger.warning(
                        f"Invalid regex pattern provided: {value} for field {field}. Error: {e}"
                    )
                    continue  # Skip this condition
            elif operator == Operator.EQ_NUM:
                if numeric_value is not None:
                    condition_query = {mongo_field: numeric_value}
                else:
                    logger.warning(
                        f"Could not convert value '{value}' to numeric for EQ_NUM operator on field {field}."
                    )
                    continue  # Skip if value is not numeric
            elif operator == Operator.GT:
                if numeric_value is not None:
                    condition_query = {mongo_field: {"$gt": numeric_value}}
                else:
                    logger.warning(
                        f"Could not convert value '{value}' to numeric for GT operator on field {field}."
                    )
                    continue
            elif operator == Operator.LT:
                if numeric_value is not None:
                    condition_query = {mongo_field: {"$lt": numeric_value}}
                else:
                    logger.warning(
                        f"Could not convert value '{value}' to numeric for LT operator on field {field}."
                    )
                    continue
            elif operator == Operator.GTE:
                if numeric_value is not None:
                    condition_query = {mongo_field: {"$gte": numeric_value}}
                else:
                    logger.warning(
                        f"Could not convert value '{value}' to numeric for GTE operator on field {field}."
                    )
                    continue
            elif operator == Operator.LTE:
                if numeric_value is not None:
                    condition_query = {mongo_field: {"$lte": numeric_value}}
                else:
                    logger.warning(
                        f"Could not convert value '{value}' to numeric for LTE operator on field {field}."
                    )
                    continue

            if condition_query:
                conditions.append(condition_query)

        elif isinstance(condition, FilterGroup):  # Handle nested groups recursively
            nested_query = build_mongo_query(condition, field_prefix=field_prefix)
            if nested_query:
                conditions.append(nested_query)

    if not conditions:
        return {}

    mongo_operator = "$and" if filter_group.type == FilterGroupType.AND else "$or"
    return {mongo_operator: conditions}


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


async def get_listing(listing_id: str) -> Optional[ListingDocument]:
    """Get a specific listing by ID."""
    return await ListingDocument.get(PydanticObjectId(listing_id))


async def get_listing_by_original_id(
    original_id: str,
) -> Optional[ListingDocument]:
    """Get a specific listing by original ID."""
    return await ListingDocument.find_one({"original_id": original_id})


async def get_analyses_by_original_ids(
    original_ids: List[str],
) -> List[AnalyzedListingDocument]:
    """Get multiple analyses by original IDs in a single query."""
    return await AnalyzedListingDocument.find(
        {"original_listing_id": {"$in": original_ids}}
    ).to_list()


async def get_analyzed_listings(
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


async def get_analyzed_listing(
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


async def get_analysis_by_original_id(
    original_id: str,
) -> Optional[AnalyzedListingDocument]:
    """Get a specific analysis by original ID."""
    return await AnalyzedListingDocument.find_one({"original_listing_id": original_id})


async def get_similar_listings(
    listing_id: str, limit: int = 6, offset: int = 0
) -> List[ListingDocument]:
    """Get similar listings based on embeddings similarity."""
    listing = await ListingDocument.get(listing_id)
    if not listing or not listing.analysis_status == AnalysisStatus.COMPLETED:
        return []

    logger.debug(f"Finding similar listings for: {listing.original_id}")

    analysis = await get_analysis_by_original_id(listing.original_id)
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


async def get_listings_with_analysis(
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    search_text: Optional[str] = None,
    filter_group: Optional[FilterGroup] = None,
    skip: int = 0,
    limit: int = 12,
) -> List[Tuple[ListingDocument, Optional[AnalyzedListingDocument]]]:
    """Get listings with optional filters and analysis data."""
    # Start building the pipeline
    pipeline: List[Dict[str, Any]] = []

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

    # Handle price filters (apply directly to ListingDocument.price_value)
    price_query_part = {}
    if price_min is not None:
        price_query_part["$gte"] = float(price_min)  # Use float
    if price_max is not None:
        price_query_part["$lte"] = float(price_max)  # Use float
    if price_query_part:
        match_conditions.append({"price_value": price_query_part})

    # Handle text search (apply directly to ListingDocument fields)
    if search_text:
        escaped_search_text = re.escape(search_text)
        match_conditions.append(
            {
                "$or": [
                    {"title": {"$regex": escaped_search_text, "$options": "i"}},
                    {"description": {"$regex": escaped_search_text, "$options": "i"}},
                ]
            }
        )

    # Handle advanced filter group (pass field_prefix='analysis' to build_mongo_query)
    if filter_group:
        # Pass 'analysis' as the prefix. build_mongo_query now handles prefixing correctly.
        advanced_filter = build_mongo_query(filter_group, field_prefix="analysis")
        if advanced_filter:
            match_conditions.append(advanced_filter)

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

    # Add projection stage to reshape the document before pagination
    # This ensures consistent field names regardless of whether analysis exists
    pipeline.append(
        {
            "$project": {
                "_id": 1,
                "original_id": 1,
                "site": 1,
                "url": 1,
                "title": 1,
                "description": 1,
                "price_str": 1,
                "price_value": 1,
                "currency": 1,
                "scraped_at": 1,
                "last_checked_at": 1,
                "photo_urls": 1,
                "analysis_status": 1,
                "created_at": 1,
                "updated_at": 1,
                # Include analysis fields, defaulting to null if analysis is missing
                "analysis": {
                    "_id": "$analysis._id",
                    "parsed_listing_id": "$analysis.parsed_listing_id",
                    "original_listing_id": "$analysis.original_listing_id",
                    "type": "$analysis.type",
                    "brand": "$analysis.brand",
                    "base_model": "$analysis.base_model",
                    "model_variant": "$analysis.model_variant",
                    "info": "$analysis.info",
                    "confidence_score": "$analysis.confidence_score",
                    "embeddings": "$analysis.embeddings",  # Consider excluding if not needed for list view
                    "created_at": "$analysis.created_at",
                    "updated_at": "$analysis.updated_at",
                },
            }
        }
    )

    # Add pagination
    pagination_params = []
    if skip != 0:
        pagination_params.append({"$skip": skip})
    if limit != 0:
        pagination_params.append({"$limit": limit})
    if pagination_params:
        pipeline.extend(pagination_params)

    logger.debug(f"Pipeline: {pipeline}")
    # Execute pipeline and convert results to Pydantic models
    results = await ListingDocument.aggregate(
        pipeline
    ).to_list()  # Use ListingDocument as the base for aggregation

    listings_with_analysis = []
    for result in results:
        # Safely pop the analysis part if it exists and is valid
        analysis_data = result.pop("analysis", None)
        listing = ListingDocument.model_validate(
            result
        )  # Validate the main listing part

        analysis = None
        # Validate analysis only if it's not None and has an _id (indicating it was present)
        if analysis_data and analysis_data.get("_id"):
            try:
                # Exclude embeddings before validation if they exist but are not needed
                # analysis_data.pop("embeddings", None)
                analysis = AnalyzedListingDocument.model_validate(analysis_data)
            except Exception as e:
                logger.error(
                    f"Failed to validate analysis data for listing {listing.original_id}: {e}. Data: {analysis_data}"
                )

        listings_with_analysis.append((listing, analysis))

    logger.debug(f"Returned {len(listings_with_analysis)} listings with analysis")
    return listings_with_analysis


async def get_distinct_info_fields() -> List[str]:
    """Get all distinct fields used in the info dictionary across all analyzed listings."""
    pipeline = [
        {"$project": {"info_fields": {"$objectToArray": "$info"}}},
        {"$unwind": "$info_fields"},
        {"$group": {"_id": "$info_fields.k"}},
        {"$sort": {"_id": 1}},
    ]

    result = await AnalyzedListingDocument.aggregate(pipeline).to_list()
    return [doc["_id"] for doc in result]


async def get_info_field_values(
    field_names: List[str], limit: int = 10
) -> Dict[str, List[Tuple[str, int]]]:
    """Get the most common values for multiple info fields in a single query.

    Args:
        field_names: List of field names to retrieve values for
        limit: Maximum number of values to return per field

    Returns:
        Dictionary mapping field names to lists of (value, count) tuples for the most common values
    """
    if not field_names:
        return {}

    try:
        # Create a single aggregation pipeline that handles all fields at once
        pipeline = [
            # Match documents with at least one of the requested fields
            {
                "$match": {
                    "$or": [
                        {f"info.{field}": {"$exists": True, "$ne": None}}
                        for field in field_names
                    ]
                }
            },
            # Unwind the info fields to process them individually
            {"$project": {"info": 1}},
            # Converts the info object to array of key-value pairs
            {"$project": {"info_entries": {"$objectToArray": "$info"}}},
            # Unwind the array to work with individual entries
            {"$unwind": "$info_entries"},
            # Filter only the fields we're interested in
            {"$match": {"info_entries.k": {"$in": field_names}}},
            # Group by field name and value, counting occurrences
            {
                "$group": {
                    "_id": {"field": "$info_entries.k", "value": "$info_entries.v"},
                    "count": {"$sum": 1},
                }
            },
            # Sort by field name and count (descending)
            {"$sort": {"_id.field": 1, "count": -1}},
        ]

        logger.debug(f"Getting common values for fields: {field_names}")
        results = await AnalyzedListingDocument.aggregate(pipeline).to_list()

        # Process the aggregation results
        field_values: Dict[str, List[Tuple[str, int]]] = {
            field: [] for field in field_names
        }
        for result in results:
            try:
                field = result["_id"]["field"]
                value = result["_id"]["value"]
                count = result["count"]

                # Only add to the result if the list for this field isn't full yet
                if field in field_values and len(field_values[field]) < limit:
                    field_values[field].append((str(value), count))
            except (KeyError, TypeError) as e:
                logger.warning(f"Error processing result: {e}")
                continue

        # Log results
        for field in field_names:
            logger.debug(
                f"Found {len(field_values[field])} common values for field: {field}"
            )

        return field_values
    except Exception as e:
        logger.error(f"Error getting values for fields {field_names}: {str(e)}")
        return {field: [] for field in field_names}


async def get_similar_listings_with_analysis(
    listing_id: str, skip: int = 0, limit: int = 12
) -> List[Tuple[ListingDocument, Optional[AnalyzedListingDocument]]]:
    """Get similar listings with their analysis data."""
    similar = await get_similar_listings(listing_id, limit, skip)
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


async def get_listing_with_analysis(
    listing_id: str,
) -> Optional[Tuple[ListingDocument, Optional[AnalyzedListingDocument]]]:
    """Get a specific listing with its analysis data."""
    listing = await ListingDocument.get(PydanticObjectId(listing_id))
    if not listing:
        return None

    analysis = await get_analysis_by_original_id(listing.original_id)
    return (listing, analysis)
