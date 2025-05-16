import logging
from typing import Any, Dict, List

from backend.schemas.field_harmonization import FieldHarmonizationMapping
from backend.schemas.listings import ListingDocument
from backend.services.analytics.field_harmonization import get_active_mappings

logger = logging.getLogger(__name__)


async def _apply_mappings_to_listing(
    info: Dict[str, Any], listing_id: str
) -> Dict[str, Any]:
    """
    Apply all active field mappings to a listing's info dictionary.

    Args:
        info: The original info dictionary from a listing
        listing_id: The original_id of the listing being processed

    Returns:
        The transformed info dictionary with mappings applied
    """
    if not info:
        return {}  # Nothing to do for empty info

    try:
        # Get all active mappings
        active_mappings = await get_active_mappings()
        if not active_mappings:
            return info  # No active mappings, return unchanged

        # Create a copy of the info dict to modify
        transformed_info = info.copy()

        # Track which mappings affected this listing
        affected_mappings = set()
        # Track fields to remove
        fields_to_remove = set()

        # For each active mapping
        for mapping in active_mappings:
            mapping_affected = False

            # Apply each field mapping
            for field_map in mapping.mappings:
                original_field = field_map.original_field
                target_field = field_map.target_field

                # Skip if original field doesn't exist
                if original_field not in info:
                    continue

                # Get the original value
                original_value = info[original_field]

                # Apply mapping - in our simplified model, we just copy the value
                if original_field != target_field:
                    if (
                        target_field not in transformed_info
                        or not transformed_info[target_field]
                    ):
                        transformed_info[target_field] = original_value
                        # Mark original field for removal
                        fields_to_remove.add(original_field)
                        mapping_affected = True

            # If this mapping affected the listing, update the affected_listings set
            if mapping_affected:
                affected_mappings.add(mapping.id)

        # Remove original fields after mapping
        for field in fields_to_remove:
            if field in transformed_info:
                del transformed_info[field]

        # Update the affected_listings field for each affected mapping
        if affected_mappings:
            # We need to use MongoDB update directly to efficiently add to the set
            collection = FieldHarmonizationMapping.get_motor_collection()

            for mapping_id in affected_mappings:
                await collection.update_one(
                    {"_id": mapping_id},
                    {"$addToSet": {"affected_listings": listing_id}},
                )

        return transformed_info

    except Exception as e:
        logger.error(f"Error applying mappings to listing {listing_id}: {str(e)}")
        return info  # In case of error, return the original info


async def save_listings(listings: List[ListingDocument]):
    """Save listings to the database.

    Deduplicates incoming listings by original_id, maintains one with more=True and most recent
    Deletes existing listings if they have identical content.
    Applies field harmonization mappings to any new or updated listings.

    Args:
        listings: List of listings to save
    """
    # Deduplicate incoming listings by original_id
    dedup_listings = {listing.original_id: listing for listing in listings}
    listings = list(dedup_listings.values())
    original_ids = [listing.original_id for listing in listings]

    # Get existing listings with the same original_ids
    existing_listings = await ListingDocument.find_many(
        {"original_id": {"$in": original_ids}}
    ).to_list()
    existing_by_id = {listing.original_id: listing for listing in existing_listings}

    # Separate listings into updates and new inserts
    to_delete_ids = []
    to_insert = []

    for listing in listings:
        existing = existing_by_id.get(listing.original_id)
        if existing:
            # Compare all fields except metadata fields
            new_dict = listing.model_dump(exclude={"id", "created_at", "updated_at"})
            existing_dict = existing.model_dump(
                exclude={"id", "created_at", "updated_at"}
            )

            if new_dict != existing_dict:
                # Content is different, mark old for deletion and new for insertion
                to_delete_ids.append(listing.original_id)
                to_insert.append(listing)
        else:
            # No existing listing, just insert
            to_insert.append(listing)

    # Delete listings that have changed
    if to_delete_ids:
        await ListingDocument.find_many(
            {"original_id": {"$in": to_delete_ids}}
        ).delete_many()
        logger.info(f"Deleted {len(to_delete_ids)} changed listings")
        [logger.debug(f"Deleted changed listing {id}") for id in to_delete_ids]

    # Insert new and changed listings - applying field mappings
    if to_insert:
        # Process each listing to apply field mappings
        for listing in to_insert:
            if hasattr(listing, "parameters") and listing.parameters:
                # Apply field harmonization mappings if parameters exist
                transformed_params = await _apply_mappings_to_listing(
                    listing.parameters, listing.original_id
                )
                listing.parameters = transformed_params

        await ListingDocument.insert_many(to_insert)
        logger.info(f"Saved {len(to_insert)} new/changed listings")
        [logger.debug(f"Saved {listing.original_id}") for listing in to_insert]
    else:
        logger.info("No new or changed listings to save")
