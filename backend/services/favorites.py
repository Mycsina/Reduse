"""Service layer for managing favorite searches."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from beanie import PydanticObjectId

from backend.schemas.analysis import AnalyzedListingDocument
from backend.schemas.favorites import (FavoriteSearchCreate,
                                       FavoriteSearchDocument,
                                       FavoriteSearchUpdate)
from backend.schemas.listings import ListingDocument
from backend.services.query import get_listings_with_analysis

logger = logging.getLogger(__name__)


async def create_favorite_search(
    user_id: PydanticObjectId, data: FavoriteSearchCreate
) -> FavoriteSearchDocument:
    """Creates a new favorite search for a user."""
    favorite = FavoriteSearchDocument(user_id=user_id, **data.model_dump())
    await favorite.insert()
    logger.info(f"Created favorite search '{favorite.name}' for user {user_id}")
    return favorite


async def get_favorite_searches_by_user(
    user_id: PydanticObjectId,
) -> List[FavoriteSearchDocument]:
    """Retrieves all favorite searches for a specific user."""
    return await FavoriteSearchDocument.find(
        FavoriteSearchDocument.user_id == user_id
    ).to_list()


async def get_favorite_searches_by_user_with_new_counts(
    user_id: PydanticObjectId,
) -> List[Dict[str, Any]]:
    """Retrieves all favorite searches for a user, including count of new listings."""
    favorites = await FavoriteSearchDocument.find(
        FavoriteSearchDocument.user_id == user_id
    ).to_list()

    enriched_favorites = []
    for fav in favorites:
        # Fetch all listings matching the favorite's query params
        # Reusing the logic from get_listings_for_favorite but adapting for counts
        query_params = fav.query_params
        all_matching_listings_tuples = await get_listings_with_analysis(
            price_min=query_params.price.min if query_params.price else None,
            price_max=query_params.price.max if query_params.price else None,
            search_text=query_params.search_text,
            filter_group=query_params.filter,
        )

        new_count = 0
        seen_ids_set = set(fav.seen_listing_ids)
        for listing_doc, _ in all_matching_listings_tuples:
            if listing_doc.id not in seen_ids_set:
                new_count += 1

        fav_dict = fav.model_dump()  # Convert to dict
        fav_dict["new_listings_count"] = new_count
        enriched_favorites.append(fav_dict)

    return enriched_favorites


async def get_favorite_search(
    favorite_id: PydanticObjectId, user_id: PydanticObjectId
) -> Optional[FavoriteSearchDocument]:
    """Retrieves a specific favorite search by its ID, ensuring it belongs to the user."""
    return await FavoriteSearchDocument.find_one(
        FavoriteSearchDocument.id == favorite_id,
        FavoriteSearchDocument.user_id == user_id,
    )


async def update_favorite_search(
    favorite_id: PydanticObjectId, user_id: PydanticObjectId, data: FavoriteSearchUpdate
) -> Optional[FavoriteSearchDocument]:
    """Updates a favorite search (e.g., renaming)."""
    favorite = await get_favorite_search(favorite_id, user_id)
    if not favorite:
        return None

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return favorite  # No changes requested

    try:
        await favorite.update({"$set": update_data})
        await favorite.reload()  # Reload to get updated data
        logger.info(f"Updated favorite search {favorite_id} for user {user_id}")
        return favorite
    except Exception as e:
        logger.error(
            f"Database error when updating favorite {favorite_id} for user {user_id}: {e}",
            exc_info=True,
        )
        return None


async def delete_favorite_search(
    favorite_id: PydanticObjectId, user_id: PydanticObjectId
) -> bool:
    """Deletes a favorite search."""
    favorite = await get_favorite_search(favorite_id, user_id)
    if not favorite:
        return False
    try:
        await favorite.delete()
        logger.info(f"Deleted favorite search {favorite_id} for user {user_id}")
        return True
    except Exception as e:
        logger.error(
            f"Database error when deleting favorite {favorite_id} for user {user_id}: {e}",
            exc_info=True,
        )
        return False


async def mark_favorite_search_viewed(
    favorite_id: PydanticObjectId,
    user_id: PydanticObjectId,
    viewed_listing_ids: List[PydanticObjectId],
) -> bool:
    """Updates the last viewed timestamp and adds viewed listing IDs."""
    favorite = await get_favorite_search(favorite_id, user_id)
    if not favorite:
        logger.warning(
            f"Attempt to mark listings seen for non-existent/unauthorized favorite {favorite_id} by user {user_id}"
        )
        return False

    update_query = {
        "$set": {"last_viewed_at": datetime.utcnow()},
        "$addToSet": {"seen_listing_ids": {"$each": viewed_listing_ids}},
    }
    try:
        await favorite.update(update_query)
        logger.info(
            f"Marked favorite search {favorite_id} as viewed for user {user_id}. "
            f"Added {len(viewed_listing_ids)} listings to seen list. "
        )
        return True
    except Exception as e:
        logger.error(
            f"Database error when marking favorite {favorite_id} as viewed for user {user_id}: {e}",
            exc_info=True,
        )
        return False


async def get_listings_for_favorite(
    favorite_id: PydanticObjectId, user_id: PydanticObjectId
) -> Tuple[
    Optional[FavoriteSearchDocument],
    List[Tuple[ListingDocument, Optional[AnalyzedListingDocument]]],
]:
    """
    Fetches a favorite search and all listings matching its query parameters.

    Returns:
        A tuple containing:
        - The FavoriteSearchDocument (or None if not found/authorized).
        - A list of tuples (ListingDocument, Optional[AnalyzedListingDocument]) matching the query.
    """
    favorite = await get_favorite_search(favorite_id, user_id)
    if not favorite:
        return None, []

    # Use the query parameters from the favorite search
    query_params = favorite.query_params
    all_matching_listings = await get_listings_with_analysis(
        price_min=query_params.price.min if query_params.price else None,
        price_max=query_params.price.max if query_params.price else None,
        search_text=query_params.search_text,
        filter_group=query_params.filter,
        # Fetch potentially more than default limit to check against seen_ids
        # TODO: Consider pagination for the underlying get_listings_with_analysis call
        # if result sets can be very large.
        limit=1000,  # Increase limit significantly for now
        skip=0,
    )

    return favorite, all_matching_listings


async def get_new_and_seen_listings_for_favorite(
    favorite_id: PydanticObjectId, user_id: PydanticObjectId
) -> Tuple[
    Optional[FavoriteSearchDocument],
    List[Tuple[ListingDocument, Optional[AnalyzedListingDocument]]],
    List[Tuple[ListingDocument, Optional[AnalyzedListingDocument]]],
]:
    """
    Fetches a favorite search, retrieves all matching listings, and separates them
    into 'new' (not seen before) and 'seen'.

    Returns:
        A tuple containing:
        - The FavoriteSearchDocument (or None if not found/authorized).
        - A list of 'new' listing tuples.
        - A list of 'seen' listing tuples.
    """
    favorite, all_listings = await get_listings_for_favorite(favorite_id, user_id)
    if not favorite:
        return None, [], []

    new_listings = []
    seen_listings = []
    seen_ids_set = set(favorite.seen_listing_ids)

    for listing, analysis in all_listings:
        if listing.id not in seen_ids_set:
            new_listings.append((listing, analysis))
        else:
            seen_listings.append((listing, analysis))

    # Optionally sort seen_listings if needed, e.g., by date
    # seen_listings.sort(key=lambda x: x[0].created_at, reverse=True)

    logger.debug(
        f"For favorite {favorite_id}, found {len(new_listings)} new and "
        f"{len(seen_listings)} seen listings."
    )
    return favorite, new_listings, seen_listings
