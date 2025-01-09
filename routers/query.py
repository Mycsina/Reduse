"""Query endpoints for listings."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from beanie.operators import And, Or, RegEx
from pydantic import BaseModel

from ..schemas.listings import ListingDocument, AnalysisStatus
from ..schemas.analyzed_listings import AnalyzedListingDocument


class ListingFilter(BaseModel):
    """Filter model for listings."""

    price_min: Optional[float] = None
    price_max: Optional[float] = None
    status: Optional[AnalysisStatus] = None
    site: Optional[str] = None
    search_text: Optional[str] = None


router = APIRouter(prefix="/listings")


@router.get("/", response_model=List[ListingDocument])
async def get_listings(
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    status: Optional[AnalysisStatus] = None,
    site: Optional[str] = None,
    search_text: Optional[str] = None,
):
    """Get listings with optional filters."""
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
    return await ListingDocument.find(query).to_list()


@router.get("/{listing_id}", response_model=ListingDocument)
async def get_listing(listing_id: str):
    """Get a specific listing by ID."""
    listing = await ListingDocument.get(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing


@router.delete("/{listing_id}")
async def delete_listing(listing_id: str):
    """Delete a listing by ID."""
    listing = await ListingDocument.get(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    await listing.delete()
    return {"message": "Listing deleted"}


@router.put("/{listing_id}", response_model=ListingDocument)
async def update_listing(listing_id: str, listing_data: ListingDocument):
    """Update a listing by ID."""
    listing = await ListingDocument.get(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    for field, value in listing_data.dict(exclude_unset=True).items():
        setattr(listing, field, value)

    await listing.save()
    return listing


@router.post("/raw", response_model=List[ListingDocument])
async def query_listings_raw(query: Dict[str, Any]):
    """Query listings using a raw MongoDB query.

    The query should be a valid MongoDB query document.
    Example: {"price_value": {"$gt": 1000, "$lt": 5000}}
    """
    try:
        return await ListingDocument.find(query).to_list()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid query format: {str(e)}")


# Analyzed Listings endpoints
analyzed_router = APIRouter(prefix="/analyzed")


@analyzed_router.get("/", response_model=List[AnalyzedListingDocument])
async def get_analyzed_listings(
    brand: Optional[str] = None,
    model: Optional[str] = None,
    original_id: Optional[str] = None,
):
    """Get analyzed listings with optional filters."""
    filters = []

    if brand:
        filters.append(RegEx(AnalyzedListingDocument.brand, f".*{brand}.*", "i"))
    if model:
        filters.append(RegEx(AnalyzedListingDocument.model, f".*{model}.*", "i"))
    if original_id:
        filters.append(AnalyzedListingDocument.original_listing_id == original_id)

    query = And(*filters) if filters else {}
    return await AnalyzedListingDocument.find(query).to_list()


@analyzed_router.get("/{analyzed_id}", response_model=AnalyzedListingDocument)
async def get_analyzed_listing(analyzed_id: str):
    """Get a specific analyzed listing by ID."""
    analyzed = await AnalyzedListingDocument.get(analyzed_id)
    if not analyzed:
        raise HTTPException(status_code=404, detail="Analyzed listing not found")
    return analyzed


@analyzed_router.delete("/{analyzed_id}")
async def delete_analyzed_listing(analyzed_id: str):
    """Delete an analyzed listing by ID."""
    analyzed = await AnalyzedListingDocument.get(analyzed_id)
    if not analyzed:
        raise HTTPException(status_code=404, detail="Analyzed listing not found")
    await analyzed.delete()
    return {"message": "Analyzed listing deleted"}


@analyzed_router.put("/{analyzed_id}", response_model=AnalyzedListingDocument)
async def update_analyzed_listing(analyzed_id: str, analyzed_data: AnalyzedListingDocument):
    """Update an analyzed listing by ID."""
    analyzed = await AnalyzedListingDocument.get(analyzed_id)
    if not analyzed:
        raise HTTPException(status_code=404, detail="Analyzed listing not found")

    for field, value in analyzed_data.dict(exclude_unset=True).items():
        setattr(analyzed, field, value)

    await analyzed.save()
    return analyzed


@analyzed_router.post("/raw", response_model=List[AnalyzedListingDocument])
async def query_analyzed_listings_raw(query: Dict[str, Any]):
    """Query analyzed listings using a raw MongoDB query.

    The query should be a valid MongoDB query document.
    Example: {"brand": {"$regex": "Toyota", "$options": "i"}}
    """
    try:
        return await AnalyzedListingDocument.find(query).to_list()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid query format: {str(e)}")
