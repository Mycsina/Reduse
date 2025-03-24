"""Analytics logic for listings."""

import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from ..ai.providers.factory import create_provider
from ..config import PROVIDER_TYPE
from ..schemas.analysis import AnalyzedListingDocument
from ..schemas.analytics import FieldMapping, ModelPriceStats
from ..services.analytics import (apply_field_mapping,
                                  create_new_field_mapping,
                                  get_active_field_mapping,
                                  get_field_mapping_history,
                                  get_model_price_history,
                                  preview_field_mapping_reversion,
                                  revert_field_mappings)
from ..services.query import get_distinct_info_fields, get_info_field_values

logger = logging.getLogger(__name__)

# Initialize AI provider for embeddings
embeddings_provider = create_provider(PROVIDER_TYPE.GOOGLE)
llm_provider = create_provider(PROVIDER_TYPE.GROQ, model="llama-3.2-1b-preview")

# Cache configuration
PROTECTED_FIELDS = {"type", "brand", "base_model", "model_variant"}
MIN_OCCURRENCE_THRESHOLD = (
    5  # Minimum number of occurrences for a field to be considered common
)


async def _get_most_common_values_cached(
    field_names_tuple: Tuple[str, ...], limit: int = 10
) -> Dict[str, List[Tuple[str, int]]]:
    """Internal cached function to get the most common values for fields.

    Args:
        field_names_tuple: Tuple of field names to get values for
        limit: Maximum number of values to return per field

    Returns:
        Dictionary mapping field names to lists of (value, count) tuples
    """
    try:
        # Convert tuple back to list for the actual query
        field_names = list(field_names_tuple)
        # Get fresh values for all fields at once
        return await get_info_field_values(field_names, limit)
    except Exception as e:
        logger.error(f"Error getting values for fields {field_names_tuple}: {str(e)}")
        # Return empty results for failed fields
        return {field: [] for field in field_names_tuple}


async def get_most_common_values(
    field_names: Union[str, List[str]], limit: int = 10
) -> Union[List[Tuple[str, int]], Dict[str, List[Tuple[str, int]]]]:
    """Get the most common values for one or more fields.

    Args:
        field_names: Single field name or list of field names to get values for
        limit: Maximum number of values to return per field

    Returns:
        If field_names is a string: List of (value, count) tuples
        If field_names is a list: Dictionary mapping field names to lists of (value, count) tuples
    """
    # Convert single field name to list for consistent processing
    if isinstance(field_names, str):
        field_names = [field_names]
        single_field = True
    else:
        single_field = False

    # Convert list to tuple for caching
    field_names_tuple = tuple(field_names)
    result = await _get_most_common_values_cached(field_names_tuple, limit)

    # Return appropriate format based on input type
    if single_field:
        return result.get(field_names[0], [])
    return result


async def get_price_history(base_model: str, days: int = 30) -> List[ModelPriceStats]:
    """Get price history for a specific model.

    Args:
        base_model: The base model to get history for
        days: Number of days of history to retrieve

    Returns:
        List of price statistics ordered by timestamp
    """
    return await get_model_price_history(base_model, days)


def detect_value_pattern(values: List[Tuple[str, int]]) -> Dict[str, Any]:
    """Detect patterns in field values to help determine if fields should be fused.

    Args:
        values: List of (value, count) tuples

    Returns:
        Dict containing pattern information:
        - type: "numeric", "categorical", "boolean", "unknown"
        - patterns: List of detected patterns
        - unit: Optional unit suffix if numeric
        - stats: Optional statistics for numeric values
    """
    if not values:
        return {"type": "unknown", "patterns": [], "unit": None, "stats": None}

    # Get all values and their total count
    all_values = []
    total_count = 0
    for value, count in values:
        all_values.append(value)
        total_count += count

    # Try to detect numeric values with units
    numeric_pattern = re.compile(r"^([\d,.]+)\s*([a-zA-Z%]+)$")
    numeric_values = []
    unit = None

    for value in all_values:
        match = numeric_pattern.match(value)
        if match:
            try:
                num = float(match.group(1).replace(",", ""))
                numeric_values.append(num)
                if not unit:
                    unit = match.group(2)
            except ValueError:
                continue

    if numeric_values:
        return {
            "type": "numeric",
            "patterns": ["numeric_with_unit"],
            "unit": unit,
            "stats": {
                "min": min(numeric_values),
                "max": max(numeric_values),
                "avg": sum(numeric_values) / len(numeric_values),
            },
        }

    # Check for boolean patterns
    bool_patterns = {
        "yes/no": ["yes", "no"],
        "true/false": ["true", "false"],
        "1/0": ["1", "0"],
        "on/off": ["on", "off"],
    }

    for pattern_name, bool_values in bool_patterns.items():
        if all(v.lower() in bool_values for v in all_values):
            return {
                "type": "boolean",
                "patterns": [pattern_name],
                "unit": None,
                "stats": None,
            }

    # Check for categorical patterns
    if len(set(all_values)) <= 10:  # Arbitrary threshold for categorical
        return {
            "type": "categorical",
            "patterns": ["finite_set"],
            "unit": None,
            "stats": None,
        }

    return {"type": "unknown", "patterns": [], "unit": None, "stats": None}


async def should_fuse_fields(
    field1: str,
    field2: str,
    field1_values: List[Tuple[str, int]],
    field2_values: List[Tuple[str, int]],
    similarity: float,
) -> bool:
    """Determine if two fields should be fused based on their values and semantic similarity.

    Args:
        field1: First field name
        field2: Second field name
        field1_values: List of (value, count) tuples for first field
        field2_values: List of (value, count) tuples for second field
        similarity: Semantic similarity between field names

    Returns:
        True if fields should be fused, False otherwise
    """
    # Get value patterns for both fields
    pattern1 = detect_value_pattern(field1_values)
    pattern2 = detect_value_pattern(field2_values)

    # If both fields are numeric with same unit, fuse if similarity is high enough
    if (
        pattern1["type"] == "numeric"
        and pattern2["type"] == "numeric"
        and pattern1["unit"] == pattern2["unit"]
    ):
        return similarity >= 0.8

    # If both fields are boolean with same pattern, fuse if similarity is high enough
    if (
        pattern1["type"] == "boolean"
        and pattern2["type"] == "boolean"
        and pattern1["patterns"] == pattern2["patterns"]
    ):
        return similarity >= 0.8

    # If both fields are categorical with similar value sets, fuse if similarity is high enough
    if pattern1["type"] == "categorical" and pattern2["type"] == "categorical":
        # Calculate value set similarity
        values1 = set(v[0] for v in field1_values)
        values2 = set(v[0] for v in field2_values)
        value_similarity = len(values1.intersection(values2)) / len(
            values1.union(values2)
        )
        return value_similarity >= 0.5 and similarity >= 0.8

    # For other cases, use LLM to make the decision
    prompt = f"""
    Determine if these two fields should be fused based on their names and value patterns.
    
    Field 1: {field1}
    Pattern 1: {pattern1}
    Sample values 1: {field1_values[:5]}
    
    Field 2: {field2}
    Pattern 2: {pattern2}
    Sample values 2: {field2_values[:5]}
    
    Semantic similarity: {similarity}
    
    Consider:
    1. Do they represent the same information?
    2. Are their value patterns compatible?
    3. Would fusing them improve data consistency?
    
    Respond with only "yes" or "no".
    """

    try:
        response = await llm_provider.generate_text(
            prompt, temperature=1.0, max_tokens=10
        )
        return response.strip().lower() == "yes"
    except Exception as e:
        logger.error(f"Error using LLM for field fusion decision: {str(e)}")
        return False


async def fuse_info_fields(
    similarity_threshold: float = 0.9,
    dry_run: bool = False,
    use_llm: bool = True,
    min_occurrence: int = MIN_OCCURRENCE_THRESHOLD,
) -> Dict[str, Any]:
    """Fuse semantically similar fields from listings using value patterns and LLM.

    Args:
        similarity_threshold: Threshold for considering fields similar
        dry_run: If True, only generate mapping without applying it
        use_llm: Whether to use LLM for ambiguous cases
        min_occurrence: Minimum occurrences for a field to be considered

    Returns:
        Dictionary with field mapping and impact report
    """
    try:
        start_time = time.time()

        # Get current field mapping
        current_mapping = await get_active_field_mapping()
        existing_mappings = current_mapping.mappings if current_mapping else {}

        # Collect all unique field names
        field_names = await get_distinct_info_fields()
        logger.info(f"Found {len(field_names)} unique field names")

        # Filter fields by minimum occurrence
        if min_occurrence > 0:
            filtered_fields = []
            # Get values for all fields at once
            field_values_dict = await get_most_common_values(list(field_names), limit=5)
            if not isinstance(field_values_dict, dict):
                logger.error("Expected dictionary of field values")
                return {"error": "Failed to get field values"}

            for field in field_names:
                try:
                    values = field_values_dict.get(field, [])
                    counts = [int(count) for _, count in values]
                    count = sum(counts)
                    if count >= min_occurrence:
                        filtered_fields.append(field)
                except Exception as e:
                    logger.warning(f"Error getting count for field {field}: {str(e)}")
                    filtered_fields.append(field)

            logger.info(
                f"Filtered to {len(filtered_fields)} fields with >= {min_occurrence} occurrences"
            )
            field_names_list = sorted(filtered_fields)
        else:
            field_names_list = sorted(list(field_names))

        # Get embeddings for all field names
        logger.debug("Getting embeddings for field names")
        embeddings = await embeddings_provider.get_embeddings(field_names_list)

        if not embeddings or len(embeddings) != len(field_names_list):
            logger.error("Failed to get embeddings for all fields")
            return {"error": "Failed to get embeddings for all fields"}

        # Calculate similarity matrix
        similarity_matrix = cosine_similarity(np.array(embeddings))

        # Process each pair of fields
        field_mapping = {}
        field_metadata = {}
        processed = set()

        # Get values for all fields at once
        all_field_values_dict = await get_most_common_values(field_names_list)
        if not isinstance(all_field_values_dict, dict):
            logger.error("Expected dictionary of field values")
            return {"error": "Failed to get field values"}

        for i in range(len(field_names_list)):
            field1 = field_names_list[i]
            if field1 in processed:
                continue

            # Get values for field1 from pre-fetched results
            field1_values = all_field_values_dict.get(field1, [])

            for j in range(i + 1, len(field_names_list)):
                field2 = field_names_list[j]
                if field2 in processed:
                    continue

                similarity = similarity_matrix[i][j]
                if similarity < similarity_threshold:
                    continue

                # Get values for field2 from pre-fetched results
                field2_values = all_field_values_dict.get(field2, [])

                # Determine if fields should be fused
                should_fuse = await should_fuse_fields(
                    field1, field2, field1_values, field2_values, similarity
                )

                if should_fuse:
                    # Choose canonical field based on occurrence count
                    counts1 = [int(count) for _, count in field1_values]
                    counts2 = [int(count) for _, count in field2_values]
                    count1 = sum(counts1)
                    count2 = sum(counts2)

                    canonical_field = field1 if count1 >= count2 else field2
                    mapped_field = field2 if canonical_field == field1 else field1

                    field_mapping[mapped_field] = canonical_field
                    processed.add(mapped_field)

                    # Store metadata
                    if canonical_field not in field_metadata:
                        field_metadata[canonical_field] = {
                            "similar_fields": [],
                            "contexts": {},
                        }
                    field_metadata[canonical_field]["similar_fields"].append(
                        mapped_field
                    )
                    field_metadata[canonical_field]["contexts"][mapped_field] = {
                        "values": field2_values,
                        "pattern": detect_value_pattern(field2_values),
                    }

        # Add self-mappings for unprocessed fields
        for field in field_names_list:
            if field not in processed:
                field_mapping[field] = field
                processed.add(field)

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
                context = meta.get("contexts", {})
                break

        # Get occurrence count from context if available
        if context and "occurrence_count" in context:
            field_counts[field] = context["occurrence_count"]
        else:
            # Fallback - get count from DB
            try:
                values = await get_most_common_values(field, limit=1)
                field_counts[field] = sum(
                    int(count) for _, count in values if isinstance(count, (int, str))
                )
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


async def canonicalize_fields(
    product_collection_id: str,
    canonical_fields: Dict[str, List[str]],
    apply: bool = True,
) -> Dict[str, Any]:
    """Canonicalize fields in a product collection."""
    start_time = time.time()
    logging.info(f"Canonicalizing fields for collection {product_collection_id}")

    # Get all fields that need to be mapped
    all_mapped_fields = []
    for canonical, fields in canonical_fields.items():
        all_mapped_fields.extend(fields)

    # Process fields in batches to avoid pipeline limits
    BATCH_SIZE = 100
    field_batches = [
        all_mapped_fields[i : i + BATCH_SIZE]
        for i in range(0, len(all_mapped_fields), BATCH_SIZE)
    ]

    # Get occurrence counts for all fields
    field_counts = {}
    for batch in field_batches:
        field_names = await get_distinct_info_fields()
        for field in batch:
            if field in field_names:
                field_counts[field] = field_names[field]

    # Create mapping statistics
    mappings = []
    total_affected_docs = 0

    # Process each canonical field
    for canonical_field, mapped_fields in canonical_fields.items():
        affected_docs = 0

        # Calculate total affected documents
        for field in mapped_fields:
            if field in field_counts:
                affected_docs = max(affected_docs, field_counts.get(field, 0))

        total_affected_docs += affected_docs

        mappings.append(
            {
                "canonical_field": canonical_field,
                "mapped_fields": mapped_fields,
                "affected_documents": affected_docs,
            }
        )

    # Apply the canonicalization if requested
    if apply:
        # Process mapping in batches to avoid large updates
        processed_count = 0
        batch_size = 1000  # Process 1000 documents at a time

        for mapping in mappings:
            canonical_field = mapping["canonical_field"]
            mapped_fields = mapping["mapped_fields"]

            # Skip if no fields to map
            if not mapped_fields:
                continue

            # Process documents in batches
            skip = 0
            while True:
                cursor = AnalyzedListingDocument.find(
                    {"original_listing_id": {"$exists": True}},
                    limit=batch_size,
                    skip=skip,
                )

                # Fetch documents for this batch
                docs = await cursor.to_list()
                if not docs:
                    break

                # Update each document
                updates = []
                for doc in docs:
                    doc_update = False
                    for field in mapped_fields:
                        if field != canonical_field and field in doc.info:
                            # Only update if the field exists in this document
                            if (
                                canonical_field not in doc.info
                                or not doc.info[canonical_field]
                            ):
                                doc.info[canonical_field] = doc.info[field]
                                doc_update = True

                    if doc_update:
                        updates.append(doc)

                # Save updates
                if updates:
                    try:
                        # Use insert_many for bulk operations
                        await AnalyzedListingDocument.insert_many(updates)
                        processed_count += len(updates)

                        # Log progress
                        if processed_count % 5000 == 0:
                            logging.info(
                                f"Canonicalized {processed_count} documents..."
                            )
                    except Exception as e:
                        logging.error(f"Error saving canonicalized documents: {str(e)}")

                skip += batch_size

    # Return result
    end_time = time.time()
    execution_time = round(end_time - start_time, 2)

    result = {
        "mappings": mappings,
        "total_canonical_fields": len(canonical_fields),
        "total_mapped_fields": len(all_mapped_fields),
        "total_affected_documents": total_affected_docs,
        "execution_time": execution_time,
    }

    if apply:
        result["applied"] = True
        result["processed_documents"] = processed_count
    else:
        result["applied"] = False

    return result
