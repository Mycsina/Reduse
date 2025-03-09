"""Analytics logic for listings."""

import logging
from typing import Dict, List, Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from ..ai.providers.google import GoogleAIProvider
from ..logic.query import get_distinct_info_fields
from ..schemas.analytics import FieldMapping, ModelPriceStats
from ..services.analytics import (apply_field_mapping,
                                  create_new_field_mapping,
                                  get_active_field_mapping,
                                  get_field_mapping_history,
                                  get_model_price_history,
                                  preview_field_mapping_reversion,
                                  revert_field_mappings)

logger = logging.getLogger(__name__)

# Initialize AI provider for embeddings
provider = GoogleAIProvider()


async def get_price_history(base_model: str, days: int = 30) -> List[ModelPriceStats]:
    """Get price history for a specific model.

    Args:
        base_model: The base model to get history for
        days: Number of days of history to retrieve

    Returns:
        List of price statistics ordered by timestamp
    """
    return await get_model_price_history(base_model, days)


async def calculate_field_similarity(
    field_names: List[str],
    embeddings: List[List[float]],
    similarity_threshold: float = 0.8,
) -> Dict[str, str]:
    """Calculate semantic similarity between fields and create mapping.

    Args:
        field_names: List of field names to process
        embeddings: List of embeddings for each field name
        similarity_threshold: Threshold for considering fields similar (default: 0.8)

    Returns:
        Dictionary mapping each field to its canonical form
    """
    # Convert embeddings to numpy array for similarity calculation
    embeddings_array = np.array(embeddings)

    # Calculate cosine similarity between all pairs of embeddings
    similarity_matrix = cosine_similarity(embeddings_array)

    # Create mapping from each field to its canonical form
    field_mapping = {}
    processed = set()

    # For each field, find semantically similar fields and map to the shortest name
    for i, field in enumerate(field_names):
        if field in processed:
            continue

        # Find similar fields
        similar_indices = np.where(similarity_matrix[i] > similarity_threshold)[0]
        similar_fields = [field_names[j] for j in similar_indices]

        # Use the shortest field name as canonical form
        canonical = min(similar_fields, key=len)

        # Map all similar fields to the canonical form
        for similar_field in similar_fields:
            field_mapping[similar_field] = canonical
            processed.add(similar_field)

    return field_mapping


async def fuse_info_fields(
    similarity_threshold: float = 0.9, dry_run: bool = False
) -> Dict[str, str]:
    """Fuse semantically similar fields from listings using embeddings.

    This function:
    1. Collects all unique field names from the listings
    2. Gets embeddings for each field name
    3. Creates a mapping from each field to its canonical form using semantic similarity
    4. Applies the mapping using the analytics service

    Args:
        listings: List of analyzed listings to process
        similarity_threshold: Threshold for considering fields similar (default: 0.8)

    Returns:
        Dictionary mapping each field to its canonical form
    """
    try:
        # Collect all unique field names
        field_names = await get_distinct_info_fields()
        logger.info(f"Found {len(field_names)} unique field names")
        field_names_list = sorted(list(field_names))  # Sort for consistent ordering

        # Get embeddings for all field names
        logger.debug("Getting embeddings for field names")
        embeddings = await provider.get_embeddings(field_names_list)

        if not embeddings or len(embeddings) != len(field_names_list):
            logger.error("Failed to get embeddings for all fields")
            return {}

        # Calculate field similarity and create mapping
        field_mapping = await calculate_field_similarity(
            field_names_list, embeddings, similarity_threshold
        )

        # Create and apply the field mapping
        if not dry_run:
            mapping_doc = await create_new_field_mapping(field_mapping)
            if mapping_doc and hasattr(mapping_doc, "id"):
                await apply_field_mapping(str(mapping_doc.id))

        # Log the field mapping
        logger.debug(f"Field mapping: {field_mapping}")
        return field_mapping

    except Exception as e:
        logger.error(f"Error in fuse_info_fields: {str(e)}")
        return {}


async def get_field_mappings(days: int = 30) -> List[FieldMapping]:
    """Get history of field mappings.

    Args:
        days: Number of days of history to retrieve

    Returns:
        List of field mapping documents ordered by creation date
    """
    return await get_field_mapping_history(days)


async def get_current_field_mapping() -> Optional[FieldMapping]:
    """Get the currently active field mapping.

    Returns:
        The active field mapping document or None if not found
    """
    return await get_active_field_mapping()


async def preview_mapping_reversion(mapping_ids: List[str]) -> Dict:
    """Preview changes that would be made by reverting field mappings.

    Args:
        mapping_ids: List of mapping IDs to preview reversion for

    Returns:
        Dictionary showing preview of changes for each mapping
    """
    return await preview_field_mapping_reversion(mapping_ids)


async def revert_mappings(mapping_ids: List[str], dry_run: bool = True) -> List:
    """Revert changes made by field mapping operations.

    Args:
        mapping_ids: List of mapping IDs to revert
        dry_run: If True, only preview changes without applying them

    Returns:
        List of reversion results, one per mapping ID
    """
    return await revert_field_mappings(mapping_ids, dry_run)
