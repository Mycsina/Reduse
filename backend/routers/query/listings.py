"""Listing query endpoints."""

import logging
import traceback
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...logic import query as query_logic
from ...schemas.analysis import AnalyzedListingDocument
from ...schemas.filtering import ListingQuery
from ...schemas.listings import ListingDocument

logger = logging.getLogger(__name__)


class ListingResponse(BaseModel):
    """Response model for listing queries."""

    listing: ListingDocument
    analysis: Optional[AnalyzedListingDocument]


class NaturalLanguageQueryRequest(BaseModel):
    """Request model for natural language query."""

    query: str = Field(..., description="Natural language query string")


class InfoFieldsResponse(BaseModel):

    main_fields: List[str]
    info_fields: List[str]


router = APIRouter(prefix="/listings")


@router.post("/", response_model=List[ListingResponse])
async def query_listings(query: ListingQuery):
    """Query listings with optional analysis data."""
    logger.debug(f"Querying listings with query: {query.model_dump_json()}")
    try:
        results = await query_logic.get_listings_with_analysis(
            price_min=query.price.min if query.price else None,
            price_max=query.price.max if query.price else None,
            search_text=query.search_text,
            filter_group=query.filter,
            skip=query.skip,
            limit=query.limit,
        )
        return [ListingResponse(listing=result[0], analysis=result[1]) for result in results]
    except Exception as e:
        logger.error(f"Error querying listings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/similar/{listing_id}", response_model=List[ListingResponse])
async def get_similar_listings(
    listing_id: str,
    skip: int = 0,
    limit: int = 12,
):
    """Get similar listings with optional analysis data."""
    try:
        results = await query_logic.get_similar_listings_with_analysis(
            listing_id=listing_id,
            skip=skip,
            limit=limit,
        )
        return [ListingResponse(listing=result[0], analysis=result[1]) for result in results]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query error: {str(e)}")


@router.get("/by_id/{listing_id}", response_model=ListingResponse)
async def get_listing(listing_id: str):
    """Get a specific listing with its analysis data."""
    result = await query_logic.get_listing_with_analysis(listing_id)
    if not result:
        raise HTTPException(status_code=404, detail="Listing not found")
    return ListingResponse(listing=result[0], analysis=result[1])


@router.get("/fields", response_model=InfoFieldsResponse)
async def get_available_fields():
    """Get all available fields for filtering."""
    main_fields = ["type", "brand", "base_model", "model_variant"]
    info_fields = await query_logic.get_distinct_info_fields()
    return InfoFieldsResponse(main_fields=main_fields, info_fields=info_fields)


@router.post("/natural", response_model=ListingQuery)
async def natural_language_query(request: NaturalLanguageQueryRequest):
    """
    Process a natural language query and return a structured ListingQuery.

    This endpoint converts a natural language description into a structured query
    that can be used with the standard listing query endpoint.
    """
    try:
        return await query_logic.process_natural_language_query(request.query)
    except Exception as e:
        raise e
        logger.error(f"Error processing natural language query: {e}")
        raise HTTPException(status_code=500, detail=str(e))
