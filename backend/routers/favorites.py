"""API endpoints for managing favorite searches."""

import logging
from typing import List, Optional, Tuple

from beanie import PydanticObjectId
from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel

from backend.auth import current_active_user  # Correct path
from backend.schemas.analysis import AnalyzedListingDocument  # Correct path
from backend.schemas.favorites import FavoriteSearchCreate  # Correct path
from backend.schemas.favorites import (FavoriteSearchDocument,
                                       FavoriteSearchRead,
                                       FavoriteSearchUpdate)
from backend.schemas.listings import ListingDocument  # Correct path
from backend.schemas.users import User  # Correct path
from backend.services.favorites import (  # Correct path
    create_favorite_search, delete_favorite_search, get_favorite_search,
    get_favorite_searches_by_user_with_new_counts,
    get_new_and_seen_listings_for_favorite, mark_favorite_search_viewed,
    update_favorite_search)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/favorites",
    tags=["favorites"],
    dependencies=[Depends(current_active_user)],  # Protect all routes in this router
)


# Define a response model for the listings split
class FavoriteListingsResponse(BaseModel):
    favorite: FavoriteSearchRead
    new_listings: List[Tuple[ListingDocument, Optional[AnalyzedListingDocument]]]
    seen_listings: List[Tuple[ListingDocument, Optional[AnalyzedListingDocument]]]

    class Config:
        arbitrary_types_allowed = True  # Allow tuple types


@router.post(
    "/", response_model=FavoriteSearchRead, status_code=status.HTTP_201_CREATED
)
async def add_favorite_search(
    favorite_data: FavoriteSearchCreate,
    user: User = Depends(current_active_user),
) -> FavoriteSearchRead:
    """Add a new favorite search for the current user."""
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User ID is missing for authenticated user",
        )
    created_favorite = await create_favorite_search(user_id=user.id, data=favorite_data)
    # Convert Document to Read model before returning
    # By calling .model_dump(), we provide a dict, which model_validate handles robustly.
    return FavoriteSearchRead.model_validate(created_favorite.model_dump())


@router.get("/", response_model=List[FavoriteSearchRead])
async def list_favorite_searches(
    user: User = Depends(current_active_user),
) -> List[FavoriteSearchRead]:
    """List all favorite searches for the current user."""
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User ID is missing for authenticated user",
        )
    favorites_data = await get_favorite_searches_by_user_with_new_counts(
        user_id=user.id
    )
    # Each item in favorites_data is a dict, model_validate will create FavoriteSearchRead instances
    return [FavoriteSearchRead.model_validate(fav_data) for fav_data in favorites_data]


@router.get("/{favorite_id}", response_model=FavoriteSearchRead)
async def get_single_favorite_search(
    favorite_id: PydanticObjectId,
    user: User = Depends(current_active_user),
) -> FavoriteSearchRead:
    """Get a specific favorite search by ID."""
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User ID is missing for authenticated user",
        )
    favorite = await get_favorite_search(favorite_id=favorite_id, user_id=user.id)
    if not favorite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Favorite search not found"
        )
    return FavoriteSearchRead.model_validate(favorite)


@router.patch("/{favorite_id}", response_model=FavoriteSearchRead)
async def update_single_favorite_search(
    favorite_id: PydanticObjectId,
    update_data: FavoriteSearchUpdate,
    user: User = Depends(current_active_user),
) -> FavoriteSearchRead:
    """Update a favorite search (e.g., rename)."""
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User ID is missing for authenticated user",
        )
    updated_favorite = await update_favorite_search(
        favorite_id=favorite_id, user_id=user.id, data=update_data
    )
    if not updated_favorite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Favorite search not found"
        )
    return FavoriteSearchRead.model_validate(updated_favorite)


@router.delete("/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_single_favorite_search(
    favorite_id: PydanticObjectId,
    user: User = Depends(current_active_user),
) -> None:
    """Delete a favorite search."""
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User ID is missing for authenticated user",
        )
    deleted = await delete_favorite_search(favorite_id=favorite_id, user_id=user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Favorite search not found"
        )
    return None  # Return No Content on successful deletion


@router.get("/{favorite_id}/listings", response_model=FavoriteListingsResponse)
async def get_favorite_listings_split(
    favorite_id: PydanticObjectId,
    user: User = Depends(current_active_user),
):
    """Get listings for a favorite search, split into new and seen."""
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User ID is missing for authenticated user",
        )
    favorite, new_listings, seen_listings = (
        await get_new_and_seen_listings_for_favorite(
            favorite_id=favorite_id, user_id=user.id
        )
    )
    if not favorite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Favorite search not found"
        )

    # Manually encode the response to handle PydanticObjectId within tuples
    # Pydantic v2 might handle this better, but being explicit is safer
    encoded_new = [
        (
            ListingDocument.model_validate(l).model_dump(),
            AnalyzedListingDocument.model_validate(a).model_dump() if a else None,
        )
        for l, a in new_listings
    ]
    encoded_seen = [
        (
            ListingDocument.model_validate(l).model_dump(),
            AnalyzedListingDocument.model_validate(a).model_dump() if a else None,
        )
        for l, a in seen_listings
    ]

    response_data = {
        "favorite": FavoriteSearchRead.model_validate(favorite).model_dump(),
        "new_listings": encoded_new,
        "seen_listings": encoded_seen,
    }
    return response_data


class MarkSeenRequest(BaseModel):
    listing_ids: List[PydanticObjectId]


@router.patch("/{favorite_id}/mark_seen", status_code=status.HTTP_204_NO_CONTENT)
async def mark_listings_as_seen(
    favorite_id: PydanticObjectId,
    request_body: MarkSeenRequest = Body(...),
    user: User = Depends(current_active_user),
):
    """Mark a list of listing IDs as seen for a specific favorite search."""
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User ID is missing for authenticated user",
        )
    if not request_body.listing_ids:
        # Nothing to mark, return success without DB call
        return None

    success = await mark_favorite_search_viewed(
        favorite_id=favorite_id,
        user_id=user.id,
        viewed_listing_ids=request_body.listing_ids,
    )
    if not success:
        # This could happen if the favorite_id doesn't exist or doesn't belong to the user
        # get_favorite_search within mark_favorite_search_viewed handles this check
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite search not found or no updates made",
        )
    return None
