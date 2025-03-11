"""Analytics logic for listings."""

import json
import logging
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity

from ..ai.providers.factory import create_provider
from ..ai.providers.google import GoogleAIProvider
from ..logic.query import get_distinct_info_fields
from ..schemas.analytics import FieldMapping, FieldValueStats, ModelPriceStats
from ..services.analytics import (apply_field_mapping,
                                  create_new_field_mapping,
                                  get_active_field_mapping,
                                  get_field_mapping_history,
                                  get_model_price_history,
                                  preview_field_mapping_reversion,
                                  revert_field_mappings)
from ..services.query import get_info_field_values

logger = logging.getLogger(__name__)

# Initialize AI provider for embeddings
provider = GoogleAIProvider()
llm_provider = create_provider()

# Cache configuration
CACHE_TTL_SECONDS = 3600  # 1 hour cache for field values
PROTECTED_FIELDS = {"type", "brand", "base_model", "model_variant"}
MIN_OCCURRENCE_THRESHOLD = (
    5  # Minimum number of occurrences for a field to be considered common
)


async def get_price_history(base_model: str, days: int = 30) -> List[ModelPriceStats]:
    """Get price history for a specific model.

    Args:
        base_model: The base model to get history for
        days: Number of days of history to retrieve

    Returns:
        List of price statistics ordered by timestamp
    """
    return await get_model_price_history(base_model, days)


@lru_cache(maxsize=100)
def cached_get_field_values(field_name: str, limit: int = 10) -> List[Tuple[str, int]]:
    """Cached wrapper for getting common field values.
    This function will be called by the async version with actual DB access.

    Args:
        field_name: Name of the field to get values for
        limit: Maximum number of values to return

    Returns:
        List of (value, count) tuples
    """
    # This is just a placeholder - the actual value will come from the async function
    # but we need this for the LRU cache decorator to work
    return []


async def get_most_common_values(
    field_name: str, limit: int = 10
) -> List[Tuple[str, int]]:
    """Get the most common values for a specific field.

    Args:
        field_name: Name of the field to get values for
        limit: Maximum number of values to return

    Returns:
        List of (value, count) tuples
    """
    cache_key = f"{field_name}:{limit}"
    cached_result = cached_get_field_values(field_name, limit)

    if cached_result:
        logger.debug(f"Using cached values for field {field_name}")
        return cached_result

    values = await get_info_field_values(field_name, limit)

    # Update cache
    cached_get_field_values.__wrapped__.__cache__[cache_key] = values
    return values


def detect_value_type(values: List[Tuple[str, int]]) -> str:
    """Detect the type of values in a field based on sample values.

    Args:
        values: List of (value, count) tuples

    Returns:
        String describing the value type: "numeric", "categorical", "boolean", or "mixed"
    """
    if not values:
        return "unknown"

    # Check sample values
    sample_values = [v[0] for v in values]

    # Check for boolean values
    if all(
        val.lower() in ("true", "false", "yes", "no", "0", "1") for val in sample_values
    ):
        return "boolean"

    # Check for numeric values
    numeric_count = 0
    for val in sample_values:
        try:
            float(val)
            numeric_count += 1
        except (ValueError, TypeError):
            pass

    # Determine type based on proportion of numeric values
    if numeric_count == len(sample_values):
        return "numeric"
    elif numeric_count > 0:
        return "mixed"
    else:
        return "categorical"


async def calculate_field_similarity_with_context(
    field_names: List[str],
    embeddings: List[List[float]],
    similarity_threshold: float = 0.8,
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """Enhanced version of calculate_field_similarity that uses DBSCAN clustering
    and field value context for better grouping.

    Args:
        field_names: List of field names to process
        embeddings: List of embeddings for each field name
        similarity_threshold: Base threshold for considering fields similar

    Returns:
        Tuple of (field_mapping, field_metadata)
    """
    # Convert embeddings to numpy array
    embeddings_array = np.array(embeddings)

    # Calculate similarity matrix
    similarity_matrix = cosine_similarity(embeddings_array)

    # Use DBSCAN to find clusters (set eps to 1-similarity_threshold for clustering)
    eps = 1.0 - similarity_threshold
    clustering = DBSCAN(eps=eps, min_samples=1, metric="precomputed").fit(
        1 - similarity_matrix
    )

    # Group fields by cluster
    clusters = defaultdict(list)
    for i, cluster_id in enumerate(clustering.labels_):
        clusters[cluster_id].append(i)

    # Store field metadata
    field_metadata = {}
    field_mapping = {}
    processed = set()

    # Process each cluster and collect value context
    for cluster_id, indices in clusters.items():
        if len(indices) <= 1:
            # Single field cluster, no need for mapping
            field = field_names[indices[0]]
            field_mapping[field] = field
            processed.add(field)
            continue

        # Get fields in this cluster
        cluster_fields = [field_names[i] for i in indices]
        logger.debug(f"Cluster {cluster_id}: {cluster_fields}")

        # Collect value context for ambiguous clusters
        ambiguous_cluster = False
        field_contexts = {}

        # Fields that need context for disambiguation
        for field in cluster_fields:
            # Skip if already processed (shouldn't happen with DBSCAN)
            if field in processed:
                continue

            # Get sample values for this field
            try:
                common_values = await get_most_common_values(field)
                value_type = detect_value_type(common_values)

                field_contexts[field] = {
                    "common_values": common_values,
                    "value_type": value_type,
                    "occurrence_count": sum(count for _, count in common_values),
                }

                # Flag for potential LLM review if we have different value types in the cluster
                if any(
                    ctx["value_type"] != value_type
                    for f, ctx in field_contexts.items()
                    if f != field and f in cluster_fields
                ):
                    ambiguous_cluster = True
            except Exception as e:
                logger.error(f"Error getting values for {field}: {str(e)}")
                field_contexts[field] = {
                    "common_values": [],
                    "value_type": "unknown",
                    "occurrence_count": 0,
                }

        # For ambiguous clusters, use LLM to determine canonical field
        canonical_field = None
        if ambiguous_cluster:
            # Use LLM to determine canonical field name
            canonical_field = await select_canonical_field_with_llm(
                cluster_fields, field_contexts
            )

        # If LLM didn't help or wasn't needed, use heuristics
        if not canonical_field:
            # Choose canonical field based on occurrence count first, then length
            candidates = sorted(
                [
                    (field, field_contexts.get(field, {}).get("occurrence_count", 0))
                    for field in cluster_fields
                ],
                key=lambda x: (
                    -x[1],
                    len(x[0]),
                ),  # Sort by -count (desc), then length (asc)
            )
            canonical_field = candidates[0][0]

        # Store mapping
        for field in cluster_fields:
            field_mapping[field] = canonical_field
            processed.add(field)

        # Store metadata for reporting
        field_metadata[canonical_field] = {
            "similar_fields": cluster_fields,
            "contexts": field_contexts,
        }

    return field_mapping, field_metadata


async def select_canonical_field_with_llm(
    fields: List[str], contexts: Dict[str, Any]
) -> Optional[str]:
    """Use LLM to select the best canonical field name from a set of similar fields.

    Args:
        fields: List of field names
        contexts: Dictionary of field contexts with value samples

    Returns:
        Selected canonical field name or None if LLM fails
    """
    try:
        # Prepare prompt with field names and sample values
        prompt = """
        I need to select the most appropriate canonical field name from these similar fields.
        For each field, I'll provide the name and some sample values.
        
        Please select the single best name that:
        1. Is the most standard/conventional terminology
        2. Most clearly represents the semantic meaning
        3. Is specific enough but not overly verbose
        4. Uses consistent casing (prefer snake_case)
        
        Field options:
        """

        for field in fields:
            context = contexts.get(field, {})
            values = context.get("common_values", [])
            value_type = context.get("value_type", "unknown")

            prompt += f"\n- Field: '{field}'\n"
            prompt += f"  Type: {value_type}\n"

            if values:
                sample_values = ", ".join(
                    f"'{v[0]}' (count: {v[1]})" for v in values[:5]
                )
                prompt += f"  Sample values: {sample_values}\n"

        prompt += "\nOutput the single best field name to use as the canonical name. Just the name, no explanation:"

        # Call LLM
        response = await llm_provider.generate_text(
            prompt, temperature=0.1, max_tokens=50
        )

        # Extract field name (should be just the field name)
        selected_field = response.strip()

        # Validate that the returned field is in our list
        if selected_field in fields:
            logger.info(f"LLM selected '{selected_field}' as canonical field")
            return selected_field
        else:
            logger.warning(f"LLM returned invalid field name: '{selected_field}'")
            return None

    except Exception as e:
        logger.error(f"Error using LLM for field selection: {str(e)}")
        return None


async def validate_field_mapping(
    field_mapping: Dict[str, str], existing_mappings: Optional[Dict[str, str]] = None
) -> Tuple[Dict[str, str], List[str]]:
    """Validate field mapping for conflicts and consistency.

    Args:
        field_mapping: Proposed field mapping
        existing_mappings: Existing field mappings to check against

    Returns:
        Tuple of (validated_mapping, warnings)
    """
    validated_mapping = {}
    warnings = []

    # Check for protected fields
    for original, canonical in field_mapping.items():
        # Don't map to protected fields unless they already are protected
        if canonical in PROTECTED_FIELDS and original not in PROTECTED_FIELDS:
            warnings.append(
                f"WARNING: Mapping '{original}' to protected field '{canonical}' is not allowed"
            )
            # Skip this mapping
            continue

        # Check for conflicts with existing mappings
        if existing_mappings and original in existing_mappings:
            existing_canonical = existing_mappings[original]
            if canonical != existing_canonical:
                warnings.append(
                    f"Warning: Changing mapping for '{original}' from '{existing_canonical}' to '{canonical}'"
                )

        validated_mapping[original] = canonical

    return validated_mapping, warnings


async def generate_mapping_impact_report(
    field_mapping: Dict[str, str], field_metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate a report on the impact of applying a field mapping.

    Args:
        field_mapping: Field mapping to analyze
        field_metadata: Metadata about the fields and their contexts

    Returns:
        Dictionary with impact statistics
    """
    # Count affected listings per field
    field_counts = {}
    for field, canonical in field_mapping.items():
        if field == canonical:
            continue  # Skip self-mappings

        # Get context data (if available)
        context = None
        for c_field, meta in field_metadata.items():
            if field in meta.get("similar_fields", []):
                context = meta.get("contexts", {}).get(field, {})
                break

        # Get occurrence count from context if available
        if context and "occurrence_count" in context:
            field_counts[field] = context["occurrence_count"]
        else:
            # Fallback - get count from DB
            try:
                values = await get_most_common_values(field, limit=1)
                field_counts[field] = sum(count for _, count in values)
            except Exception:
                field_counts[field] = 0

    # Calculate totals
    total_fields = len(field_mapping)
    actual_mappings = sum(1 for f, c in field_mapping.items() if f != c)
    total_affected_docs = sum(field_counts.values())

    return {
        "total_fields": total_fields,
        "total_mapped_fields": actual_mappings,
        "total_affected_documents": total_affected_docs,
        "field_counts": field_counts,
        "clusters": [
            {
                "canonical": canonical,
                "mapped_fields": meta.get("similar_fields", []),
                "field_types": {
                    field: meta.get("contexts", {})
                    .get(field, {})
                    .get("value_type", "unknown")
                    for field in meta.get("similar_fields", [])
                },
            }
            for canonical, meta in field_metadata.items()
        ],
    }


async def fuse_info_fields(
    similarity_threshold: float = 0.9,
    dry_run: bool = False,
    use_llm: bool = True,
    min_occurrence: int = MIN_OCCURRENCE_THRESHOLD,
) -> Dict[str, Any]:
    """Enhanced version: Fuse semantically similar fields from listings using a hybrid approach.

    This function:
    1. Collects all unique field names from the listings
    2. Gets embeddings for each field name
    3. Creates a mapping from each field to its canonical form using semantic similarity
    4. Uses value context and optional LLM refinement for ambiguous cases
    5. Validates the mapping for conflicts
    6. Applies the mapping using the analytics service

    Args:
        similarity_threshold: Threshold for considering fields similar (default: 0.9)
        dry_run: If True, only generate mapping without applying it
        use_llm: Whether to use LLM for ambiguous cases (default: True)
        min_occurrence: Minimum occurrences for a field to be considered (default: 5)

    Returns:
        Dictionary with field mapping and impact report
    """
    try:
        # Start timing the operation
        start_time = time.time()

        # Get current field mapping
        current_mapping = await get_current_field_mapping()
        existing_mappings = current_mapping.mappings if current_mapping else {}

        # Collect all unique field names
        field_names = await get_distinct_info_fields()
        logger.info(f"Found {len(field_names)} unique field names")

        # Apply filtering for minimum occurrence
        if min_occurrence > 0:
            filtered_fields = []
            for field in field_names:
                try:
                    values = await get_most_common_values(field, limit=1)
                    count = sum(count for _, count in values)
                    if count >= min_occurrence:
                        filtered_fields.append(field)
                except Exception as e:
                    logger.warning(f"Error getting count for field {field}: {str(e)}")
                    filtered_fields.append(field)  # Include it anyway to be safe

            logger.info(
                f"Filtered to {len(filtered_fields)} fields with >= {min_occurrence} occurrences"
            )
            field_names_list = sorted(filtered_fields)
        else:
            field_names_list = sorted(list(field_names))  # Sort for consistent ordering

        # Get embeddings for all field names
        logger.debug("Getting embeddings for field names")
        embeddings = await provider.get_embeddings(field_names_list)

        if not embeddings or len(embeddings) != len(field_names_list):
            logger.error("Failed to get embeddings for all fields")
            return {"error": "Failed to get embeddings for all fields"}

        # Calculate field similarity and create mapping with value context
        field_mapping, field_metadata = await calculate_field_similarity_with_context(
            field_names_list, embeddings, similarity_threshold
        )

        # Validate field mapping
        validated_mapping, warnings = await validate_field_mapping(
            field_mapping, existing_mappings
        )
        if warnings:
            for warning in warnings:
                logger.warning(warning)

        # Generate impact report
        impact_report = await generate_mapping_impact_report(
            validated_mapping, field_metadata
        )

        # Create and apply the field mapping
        if not dry_run:
            mapping_doc = await create_new_field_mapping(validated_mapping)
            if mapping_doc and hasattr(mapping_doc, "id"):
                affected_docs = await apply_field_mapping(str(mapping_doc.id))
                impact_report["actual_affected_documents"] = affected_docs

        # Log the field mapping
        logger.debug(f"Field mapping: {validated_mapping}")

        # Calculate execution time
        execution_time = time.time() - start_time
        logger.info(f"Field fusion completed in {execution_time:.2f} seconds")

        return {
            "mapping": validated_mapping,
            "impact": impact_report,
            "warnings": warnings,
            "execution_time_seconds": execution_time,
        }

    except Exception as e:
        logger.error(f"Error in fuse_info_fields: {str(e)}")
        return {"error": str(e)}


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
