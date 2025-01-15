"""Query endpoints for listings."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..logic import query as query_logic
from ..schemas.analyzed_listings import AnalyzedListingDocument
from ..schemas.listings import AnalysisStatus, ListingDocument


class ListingFilter(BaseModel):
    """Filter model for listings."""

    price_min: Optional[float] = None
    price_max: Optional[float] = None
    status: Optional[AnalysisStatus] = None
    site: Optional[str] = None
    search_text: Optional[str] = None


class AnalyzedListingWithOriginal(BaseModel):
    """Response model for analyzed listing with its original listing."""

    analyzed: AnalyzedListingDocument
    original: ListingDocument


router = APIRouter(prefix="/listings")
analyzed_router = APIRouter(prefix="/analyzed")


@router.get("/", response_model=List[ListingDocument])
async def get_listings(
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    status: Optional[AnalysisStatus] = None,
    site: Optional[str] = None,
    search_text: Optional[str] = None,
    skip: int = 0,
    limit: int = 12,
):
    """Get listings with optional filters and pagination."""
    return await query_logic.get_listings(
        price_min=price_min,
        price_max=price_max,
        status=status,
        site=site,
        search_text=search_text,
        skip=skip,
        limit=limit,
    )


@router.get("/by_id/{listing_id}", response_model=ListingDocument)
async def get_listing(listing_id: str):
    """Get a specific listing by ID."""
    listing = await query_logic.get_listing(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing


@router.get("/similar/by_id/{listing_id}", response_model=List[ListingDocument])
async def get_similar_listings(listing_id: str, limit: int = 6):
    """Get similar listings based on analysis results."""
    listings = await query_logic.get_similar_listings(listing_id, limit)
    if not listings:
        raise HTTPException(status_code=404, detail="No similar listings found")
    return listings


@analyzed_router.get("/", response_model=List[AnalyzedListingWithOriginal])
async def get_analyzed_listings(
    brand: Optional[str] = None,
    model: Optional[str] = None,
    original_id: List[str] = [],
    skip: int = 0,
    limit: int = 12,
):
    """Get analyzed listings with optional filters."""
    if not original_id:
        raise HTTPException(status_code=400, detail="original_id is required")
    results = await query_logic.get_analyzed_listings(
        brand=brand,
        model=model,
        original_id=original_id,
        skip=skip,
        limit=limit,
    )
    return [AnalyzedListingWithOriginal(analyzed=analyzed, original=original) for original, analyzed in results]


@analyzed_router.get("/{analyzed_id}", response_model=AnalyzedListingWithOriginal)
async def get_analyzed_listing(analyzed_id: str):
    """Get a specific analyzed listing by ID."""
    result = await query_logic.get_analyzed_listing(analyzed_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analyzed listing not found")
    original, analyzed = result
    return AnalyzedListingWithOriginal(analyzed=analyzed, original=original)


@analyzed_router.post("/raw", response_model=List[AnalyzedListingWithOriginal])
async def query_analyzed_listings_raw(query: Dict[str, Any]):
    """Query analyzed listings using a raw MongoDB query."""
    try:
        results = await query_logic.query_analyzed_listings_raw(query)
        return [AnalyzedListingWithOriginal(analyzed=analyzed, original=original) for original, analyzed in results]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid query format: {str(e)}")
