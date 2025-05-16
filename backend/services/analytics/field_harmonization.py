"""Module for field harmonization and field similarity analysis."""

import logging
import re
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import umap
from beanie import SortDirection
from pymongo import UpdateOne

from backend.ai.providers.factory import create_provider
from backend.config import PROVIDER_TYPE
from backend.schemas.analysis import AnalyzedListingDocument
from backend.schemas.field_harmonization import (
    FieldCluster,
    FieldDistribution,
    FieldHarmonizationMapping,
    FieldMapping,
    FieldMappingImpact,
    FieldType,
    FieldValuePattern,
    HarmonizationSuggestion,
    SimilarityMatrix,
)
from backend.services.embeddings import delete_all_field_embeddings, get_field_embeddings, save_field_embedding
from backend.services.query import get_distinct_info_fields, get_info_field_values

logger = logging.getLogger(__name__)

# Initialize providers for embeddings and LLM assistance
embeddings_provider = create_provider(PROVIDER_TYPE.GOOGLE)
llm_provider = create_provider(PROVIDER_TYPE.GROQ, model="llama-3.2-1b-preview")

# Constants
DEFAULT_MIN_OCCURRENCE = 5
PROTECTED_FIELDS = {"type", "brand", "base_model", "model_variant"}
MAX_SAMPLE_DOCS = 10  # Maximum number of sample documents to include in impact analysis


async def get_active_mappings() -> List[FieldHarmonizationMapping]:
    """Get all active field mappings.

    Returns:
        List of active mappings
    """
    try:
        return await FieldHarmonizationMapping.find({"is_active": True}).to_list()
    except Exception as e:
        logger.error(f"Error getting active field mappings: {str(e)}")
        return []


async def get_field_mapping_history(days: int = 30) -> List[FieldHarmonizationMapping]:
    """Get history of field mappings.

    Args:
        days: Number of days of history to retrieve

    Returns:
        List of field mapping documents ordered by relevance (active first, then by date)
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # First, get the active mappings
        active_mappings = await FieldHarmonizationMapping.find(
            {"is_active": True, "created_at": {"$gte": cutoff}}
        ).to_list()

        # Then get the inactive mappings
        inactive_mappings = (
            await FieldHarmonizationMapping.find({"is_active": False, "created_at": {"$gte": cutoff}})
            .sort([("created_at", SortDirection.DESCENDING)])
            .to_list()
        )

        # Combine the results with active mappings first
        return active_mappings + inactive_mappings
    except Exception as e:
        logger.error(f"Error getting field mapping history: {str(e)}")
        return []


async def get_field_distribution(
    min_occurrence: int = DEFAULT_MIN_OCCURRENCE,
    include_values: bool = True,
    top_values_limit: int = 10,
) -> List[FieldDistribution]:
    """
    Get distribution statistics for all fields.

    Args:
        min_occurrence: Minimum occurrences for a field to be included
        include_values: Whether to include top values in the response
        top_values_limit: Maximum number of top values to include per field

    Returns:
        List of field distribution statistics
    """
    try:
        # Get all unique field names
        distinct_field_names = await get_distinct_info_fields()

        # Aggregate counts for each field
        pipeline = [
            {"$match": {"info": {"$exists": True}}},
            {"$project": {"info_kv": {"$objectToArray": "$info"}}},
            {"$unwind": "$info_kv"},
            {"$group": {"_id": "$info_kv.k", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gte": min_occurrence}}},
            {"$project": {"field_name": "$_id", "count": 1, "_id": 0}},
        ]
        field_counts_result = await AnalyzedListingDocument.get_motor_collection().aggregate(pipeline).to_list(None)

        # Create a dictionary for quick lookup
        field_counts_dict = {item["field_name"]: item["count"] for item in field_counts_result}

        # Filter distinct names based on counts fetched
        filtered_field_names = [name for name in distinct_field_names if name in field_counts_dict]

        if not filtered_field_names:
            logger.warning(f"No fields with >= {min_occurrence} occurrences found")
            return []

        # For each field, get distribution statistics
        distributions = []

        # Get active mappings to mark fields that are already mapped
        active_mappings = await get_active_mappings()
        mapped_fields = {}
        clusters = {}

        if active_mappings:
            # Build mapping from original fields to target fields
            for mapping in active_mappings:
                for field_map in mapping.mappings:
                    original_field = field_map.original_field
                    target_field = field_map.target_field

                    if original_field != target_field:
                        if target_field not in clusters:
                            cluster_id = str(uuid.uuid4())
                            clusters[target_field] = cluster_id

                        mapped_fields[original_field] = clusters[target_field]

        # Get values for all fields if needed
        field_values_dict = {}
        if include_values:
            field_values_dict = await get_info_field_values(filtered_field_names, limit=top_values_limit)

        for field in filtered_field_names:
            # Get the count from the aggregated results
            count = field_counts_dict[field]

            top_values = []
            if include_values:
                top_values = field_values_dict.get(field, [])

            # Detect field type and pattern
            field_type, pattern = await detect_field_type(field, top_values)

            # Create distribution object
            distribution = FieldDistribution(
                field_name=field,
                occurrence_count=count,
                distinct_value_count=len(top_values) if top_values else 0,
                top_values=top_values,
                field_type=field_type,
                pattern=pattern,
                cluster_id=mapped_fields.get(field),
            )

            distributions.append(distribution)

        return distributions

    except Exception as e:
        logger.error(f"Error getting field distribution: {str(e)}")
        return []


async def detect_field_type(
    field_name: str, values: List[Tuple[str, int]]
) -> Tuple[FieldType, Optional[FieldValuePattern]]:
    """
    Detect the type and pattern of a field based on its values.

    Args:
        field_name: Name of the field
        values: List of (value, count) tuples for the field

    Returns:
        Tuple of (field_type, pattern)
    """
    if not values:
        return FieldType.UNKNOWN, None

    # Extract just the values
    all_values = [value for value, _ in values]

    # Check if numeric with units
    numeric_pattern = re.compile(r"^([\d,.]+)\s*([a-zA-Z%]+)?$")
    numeric_count = 0
    unit = None
    numeric_values = []

    for value in all_values:
        if not isinstance(value, str):
            continue

        match = numeric_pattern.match(value.strip())
        if match:
            try:
                num = float(match.group(1).replace(",", ""))
                numeric_values.append(num)
                numeric_count += 1

                # Capture unit if present
                if match.group(2) and not unit:
                    unit = match.group(2)
            except ValueError:
                pass

    # If most values are numeric
    if len(all_values) > 0 and numeric_count / len(all_values) > 0.7:
        pattern = FieldValuePattern(
            type=FieldType.NUMERIC,
            unit=unit,
            distinct_values=len(set(all_values)),
            value_examples=all_values[:5],
            stats={
                "min": min(numeric_values) if numeric_values else None,
                "max": max(numeric_values) if numeric_values else None,
                "avg": sum(numeric_values) / len(numeric_values) if numeric_values else None,
            },
        )
        return FieldType.NUMERIC, pattern

    # Check if boolean
    bool_values = {"yes", "no", "true", "false", "1", "0", "on", "off"}
    if all(v.lower() in bool_values for v in all_values if isinstance(v, str)):
        pattern = FieldValuePattern(
            type=FieldType.BOOLEAN,
            distinct_values=len(set(all_values)),
            value_examples=all_values,
        )
        return FieldType.BOOLEAN, pattern

    # Check if categorical (small number of distinct values)
    if len(set(all_values)) <= 10 and len(all_values) >= 2:
        pattern = FieldValuePattern(
            type=FieldType.CATEGORICAL,
            distinct_values=len(set(all_values)),
            value_examples=all_values,
        )
        return FieldType.CATEGORICAL, pattern

    # Default to text
    pattern = FieldValuePattern(
        type=FieldType.TEXT,
        distinct_values=len(set(all_values)),
        value_examples=all_values[:5],
    )
    return FieldType.TEXT, pattern


async def suggest_field_mappings(
    similarity_threshold: float = 0.75,
    min_occurrence: int = DEFAULT_MIN_OCCURRENCE,
    protected_fields: Optional[List[str]] = None,
) -> HarmonizationSuggestion:
    """
    Suggest field mappings based on field similarities.

    Args:
        similarity_threshold: Minimum similarity score to consider fields similar
        min_occurrence: Minimum occurrences for a field to be included
        protected_fields: Fields that should not be mapped to others

    Returns:
        Suggestion object with clusters and mappings
    """
    try:
        # Get similarity matrix
        similarity_matrix = await generate_field_similarity_matrix(
            min_occurrence=min_occurrence, include_field_values=True
        )

        if not similarity_matrix.fields:
            logger.error("No fields found for suggesting mappings")
            return HarmonizationSuggestion(
                clusters=[],
                suggested_mapping={},
                impact=FieldMappingImpact(
                    total_fields=0,
                    total_mapped_fields=0,
                    total_affected_documents=0,
                    field_impacts={},
                    clusters=[],
                    before_after_samples=[],
                ),
                similarity_threshold=similarity_threshold,
            )

        # Get field distributions for additional context
        distributions = await get_field_distribution(min_occurrence=min_occurrence, include_values=True)

        # Create a mapping from field name to distribution
        field_to_dist = {dist.field_name: dist for dist in distributions}

        # Set of protected fields (should not be mapped to other fields)
        protected = set(protected_fields or [])
        protected.update(PROTECTED_FIELDS)

        # Detect clusters of similar fields
        clusters = []
        field_to_cluster = {}  # Maps each field to its cluster ID

        # First round: Group fields with high similarity
        for i, field1 in enumerate(similarity_matrix.fields):
            # Skip if field is already in a cluster or is protected
            if field1 in field_to_cluster or field1 in protected:
                continue

            # Start a new cluster with this field as canonical
            cluster_id = str(uuid.uuid4())
            canonical_field = field1
            similar_fields = []
            similarity_scores = {}

            # Find similar fields
            for j, field2 in enumerate(similarity_matrix.fields):
                if field1 == field2 or field2 in field_to_cluster or field2 in protected:
                    continue

                similarity = similarity_matrix.scores[i][j]
                if similarity >= similarity_threshold:
                    # Check compatible field types
                    if field1 in field_to_dist and field2 in field_to_dist:
                        type1 = field_to_dist[field1].field_type
                        type2 = field_to_dist[field2].field_type

                        # If types are completely incompatible, skip
                        if type1 != type2 and type1 != FieldType.UNKNOWN and type2 != FieldType.UNKNOWN:
                            if (type1 == FieldType.NUMERIC and type2 != FieldType.NUMERIC) or (
                                type1 == FieldType.BOOLEAN and type2 != FieldType.BOOLEAN
                            ):
                                continue

                    similar_fields.append(field2)
                    similarity_scores[field2] = similarity
                    field_to_cluster[field2] = cluster_id

            # Only create a cluster if there are similar fields
            if similar_fields:
                field_to_cluster[canonical_field] = cluster_id

                # Extract field patterns
                patterns = {}
                field_types = (
                    {canonical_field: field_to_dist[canonical_field].field_type}
                    if canonical_field in field_to_dist
                    else {}
                )

                for field in [canonical_field] + similar_fields:
                    if field in field_to_dist:
                        dist = field_to_dist[field]
                        patterns[field] = dist.pattern
                        field_types[field] = dist.field_type

                cluster = FieldCluster(
                    id=cluster_id,
                    canonical_field=canonical_field,
                    similar_fields=similar_fields,
                    field_types=field_types,
                    similarity_scores=similarity_scores,
                    patterns=patterns,
                )

                clusters.append(cluster)

        # Create mapping from original fields to canonical fields
        suggested_mapping = {}
        for cluster in clusters:
            for field in cluster.similar_fields:
                suggested_mapping[field] = cluster.canonical_field

        # Calculate impact
        impact = await get_field_mapping_impact(suggested_mapping)

        # Sort clusters by the number of similar fields (most similar fields first)
        sorted_clusters = sorted(clusters, key=lambda c: len(c.similar_fields), reverse=True)

        return HarmonizationSuggestion(
            clusters=sorted_clusters,
            suggested_mapping=suggested_mapping,
            impact=impact,
            similarity_threshold=similarity_threshold,
        )

    except Exception as e:
        logger.error(f"Error suggesting field mappings: {str(e)}")
        return HarmonizationSuggestion(
            clusters=[],
            suggested_mapping={},
            impact=FieldMappingImpact(
                total_fields=0,
                total_mapped_fields=0,
                total_affected_documents=0,
                field_impacts={},
                clusters=[],
                before_after_samples=[],
            ),
            similarity_threshold=similarity_threshold,
        )


async def delete_field_mapping(mapping_id: str) -> Tuple[bool, str]:
    """
    Permanently delete a field mapping.

    Args:
        mapping_id: The ID (_id) of the mapping to delete.

    Returns:
        Tuple (success: bool, message: str).
    """
    try:
        mapping = await FieldHarmonizationMapping.get(mapping_id)
        if not mapping:
            logger.warning(f"Mapping {mapping_id} not found for deletion.")
            return False, "Mapping not found."

        # Delete the mapping document itself
        await mapping.delete()
        logger.info(f"Successfully deleted mapping {mapping_id}")
        return True, "Mapping deleted successfully."

    except Exception as e:
        logger.error(f"Error deleting mapping {mapping_id}: {str(e)}", exc_info=True)
        return False, f"An internal error occurred during deletion: {str(e)}"


async def get_field_mapping_impact(field_mapping: Dict[str, str]) -> FieldMappingImpact:
    """
    Analyze the impact of applying a field mapping.

    Args:
        field_mapping: Dictionary mapping original fields to canonical forms

    Returns:
        Impact analysis
    """
    try:
        # Filter out self-mappings
        actual_mappings = {orig: canon for orig, canon in field_mapping.items() if orig != canon}

        if not actual_mappings:
            return FieldMappingImpact(
                total_fields=len(field_mapping),
                total_mapped_fields=0,
                total_affected_documents=0,
                field_impacts={},
                clusters=[],
                before_after_samples=[],
            )

        # Get field distributions to estimate impact
        all_fields = set(field_mapping.keys()).union(set(field_mapping.values()))
        distributions = await get_field_distribution(
            min_occurrence=1, include_values=True  # Get all fields regardless of occurrence count
        )

        # Create field to distribution mapping
        field_to_dist = {dist.field_name: dist for dist in distributions}

        # Calculate field impacts
        field_impacts = {}
        total_affected_docs = 0

        for orig, canon in actual_mappings.items():
            orig_dist = field_to_dist.get(orig)
            canon_dist = field_to_dist.get(canon)

            if orig_dist:
                affected_docs = orig_dist.occurrence_count
                total_affected_docs += affected_docs

                field_impacts[orig] = {
                    "mapped_to": canon,
                    "affected_documents": affected_docs,
                    "field_type": orig_dist.field_type,
                    "top_values": orig_dist.top_values[:3] if orig_dist.top_values else [],
                }

        # Organize fields into clusters
        clusters = []
        canon_to_cluster = {}

        for orig, canon in actual_mappings.items():
            if canon not in canon_to_cluster:
                cluster_id = str(uuid.uuid4())
                canon_to_cluster[canon] = {
                    "id": cluster_id,
                    "canonical_field": canon,
                    "similar_fields": [],
                    "field_types": {},
                    "similarity_scores": {},
                    "patterns": {},
                }

            cluster = canon_to_cluster[canon]
            cluster["similar_fields"].append(orig)

            if orig in field_to_dist:
                dist = field_to_dist[orig]
                cluster["field_types"][orig] = dist.field_type
                if dist.pattern:
                    cluster["patterns"][orig] = dist.pattern

            if canon in field_to_dist:
                dist = field_to_dist[canon]
                cluster["field_types"][canon] = dist.field_type
                if dist.pattern:
                    cluster["patterns"][canon] = dist.pattern

        # Convert clusters to proper objects
        for cluster_data in canon_to_cluster.values():
            cluster = FieldCluster(
                id=cluster_data["id"],
                canonical_field=cluster_data["canonical_field"],
                similar_fields=cluster_data["similar_fields"],
                field_types=cluster_data["field_types"],
                similarity_scores=cluster_data["similarity_scores"],
                patterns=cluster_data["patterns"],
            )
            clusters.append(cluster)

        # Get sample documents for before/after preview
        sample_docs = []
        # TODO: Implement actual document sampling with before/after transformation

        return FieldMappingImpact(
            total_fields=len(field_mapping),
            total_mapped_fields=len(actual_mappings),
            total_affected_documents=total_affected_docs,
            field_impacts=field_impacts,
            clusters=clusters,
            before_after_samples=sample_docs,
        )

    except Exception as e:
        logger.error(f"Error analyzing field mapping impact: {str(e)}")
        return FieldMappingImpact(
            total_fields=len(field_mapping),
            total_mapped_fields=0,
            total_affected_documents=0,
            field_impacts={},
            clusters=[],
            before_after_samples=[],
        )


async def create_field_mapping(
    name: str,
    mappings: List[FieldMapping],
    description: Optional[str] = None,
    is_active: bool = True,
    created_by: Optional[str] = None,
) -> Optional[FieldHarmonizationMapping]:
    """
    Create a new field harmonization mapping.

    Args:
        name: User-friendly name for the mapping
        mappings: List of field mappings
        description: Optional description
        is_active: Whether this mapping should be set as active
        created_by: User or process that created this mapping

    Returns:
        The created mapping document, or None if creation failed
    """
    try:
        # Validate that target fields are unique across all active mappings if this will be active
        if is_active and mappings:
            # Get all active mappings
            active_mappings = await get_active_mappings()

            # Build a set of all target fields currently in use
            existing_target_fields = set()
            for mapping in active_mappings:
                for field_map in mapping.mappings:
                    existing_target_fields.add(field_map.target_field)

            # Check for conflicts
            new_target_fields = {m.target_field for m in mappings}
            conflicts = existing_target_fields.intersection(new_target_fields)

            if conflicts:
                logger.error(f"Target field conflict in mapping creation: {conflicts}")
                return None  # Conflict found

        # Create the new mapping
        mapping = FieldHarmonizationMapping(
            name=name,
            description=description,
            mappings=mappings,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            is_active=is_active,
            created_by=created_by,
            affected_listings=set(),  # Start with empty set
        )

        await mapping.insert()
        return mapping

    except Exception as e:
        logger.error(f"Error creating field mapping: {str(e)}")
        return None


async def update_field_mapping(
    mapping_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    mappings_to_add: Optional[List[FieldMapping]] = None,
    mappings_to_remove: Optional[List[str]] = None,
    is_active: Optional[bool] = None,
) -> Optional[FieldHarmonizationMapping]:
    """
    Update an existing field mapping.

    Args:
        mapping_id: ID of the mapping to update
        name: New name (if None, keep existing)
        description: New description (if None, keep existing)
        mappings_to_add: New mappings to add
        mappings_to_remove: Original field names to remove from mapping
        is_active: Whether to set this mapping as active

    Returns:
        The updated mapping, or None if update failed
    """
    try:
        # Get the existing mapping
        mapping = await FieldHarmonizationMapping.get(mapping_id)
        if not mapping:
            logger.error(f"Mapping {mapping_id} not found")
            return None

        # Validate target field uniqueness if activating or adding new mappings
        if (is_active and not mapping.is_active) or mappings_to_add:
            # Get all active mappings except this one
            other_active_mappings = await FieldHarmonizationMapping.find(
                {"is_active": True, "_id": {"$ne": mapping.id}}
            ).to_list()

            # Current target fields from this mapping
            current_target_fields = {m.target_field for m in mapping.mappings}

            # Target fields from other active mappings
            existing_target_fields = set()
            for other_mapping in other_active_mappings:
                for field_map in other_mapping.mappings:
                    existing_target_fields.add(field_map.target_field)

            # New target fields from mappings being added
            new_target_fields = set()
            if mappings_to_add:
                new_target_fields = {m.target_field for m in mappings_to_add}

            # If deactivating some mappings via removal, exclude them from current
            if mappings_to_remove:
                for original_field in mappings_to_remove:
                    for m in mapping.mappings:
                        if m.original_field == original_field:
                            # If we're removing this mapping, exclude its target from current
                            if m.target_field in current_target_fields:
                                current_target_fields.remove(m.target_field)

            # Check conflicts between other active mappings and our final target fields
            all_target_fields = current_target_fields.union(new_target_fields)
            conflicts = existing_target_fields.intersection(all_target_fields)

            if conflicts and (is_active or mapping.is_active):
                logger.error(f"Target field conflict in mapping update: {conflicts}")
                return None  # Conflict found

        # Update the basic fields
        if name:
            mapping.name = name

        if description is not None:
            mapping.description = description

        # Apply changes to mappings
        if mappings_to_add:
            # Avoid duplicates by removing any existing mappings with same original field
            existing_originals = {m.original_field for m in mapping.mappings}
            new_mappings = [m for m in mappings_to_add if m.original_field not in existing_originals]
            mapping.mappings.extend(new_mappings)

        if mappings_to_remove:
            # Remove mappings for specified original fields
            mapping.mappings = [m for m in mapping.mappings if m.original_field not in mappings_to_remove]

        # Update activation status
        if is_active is not None and is_active != mapping.is_active:
            mapping.is_active = is_active

        mapping.updated_at = datetime.now(timezone.utc)
        await mapping.save()
        return mapping

    except Exception as e:
        logger.error(f"Error updating field mapping: {str(e)}")
        return None


async def generate_field_similarity_matrix(
    min_occurrence: int = DEFAULT_MIN_OCCURRENCE,
    include_field_values: bool = True,
) -> SimilarityMatrix:
    """
    Generate a similarity matrix for fields based on their names and optionally values.

    Args:
        min_occurrence: Minimum occurrences for a field to be included
        include_field_values: Whether to include field values in similarity calculation

    Returns:
        Similarity matrix object
    """
    try:
        # Get field distributions
        distributions = await get_field_distribution(min_occurrence=min_occurrence, include_values=include_field_values)

        if not distributions:
            logger.error("No fields found for similarity matrix")
            return SimilarityMatrix(fields=[], scores=[])

        # Extract field names
        field_names = [dist.field_name for dist in distributions]

        # Get existing embeddings from DB
        existing_embeddings = await get_field_embeddings(field_names)
        logger.info(f"Found {len(existing_embeddings)} existing embeddings for {len(field_names)} fields.")

        # Identify fields needing new embeddings
        missing_fields = [name for name in field_names if name not in existing_embeddings]
        new_embeddings = {}

        if missing_fields:
            logger.info(f"Generating embeddings for {len(missing_fields)} missing fields.")
            # Generate embeddings for missing fields
            try:
                generated_embeddings = await embeddings_provider.get_embeddings(missing_fields)
                if generated_embeddings and len(generated_embeddings) == len(missing_fields):
                    new_embeddings = dict(zip(missing_fields, generated_embeddings))
                    logger.info(f"Successfully generated {len(new_embeddings)} new embeddings.")

                    # Save new embeddings to DB
                    for field_name, embedding in new_embeddings.items():
                        await save_field_embedding(
                            field_name=field_name,
                            embedding=embedding,
                            provider=embeddings_provider.provider,
                            model=embeddings_provider.default_model,
                        )
                    logger.info(f"Saved {len(new_embeddings)} new embeddings to the database.")
                else:
                    logger.error(
                        f"Embedding generation failed or returned incorrect number of embeddings for {len(missing_fields)} fields."
                    )
            except Exception as e:
                logger.error(f"Error generating or saving embeddings for missing fields: {e}", exc_info=True)

        # Combine existing and new embeddings
        all_embeddings_dict = {**existing_embeddings, **new_embeddings}

        # Ensure we have embeddings for all requested field names in the correct order
        final_embeddings = [all_embeddings_dict.get(name) for name in field_names]

        # Filter out fields for which we couldn't get embeddings
        valid_indices = [i for i, emb in enumerate(final_embeddings) if emb is not None]
        if len(valid_indices) < len(field_names):
            logger.warning(
                f"Could not retrieve or generate embeddings for {len(field_names) - len(valid_indices)} fields. Proceeding with available embeddings."
            )
            field_names = [field_names[i] for i in valid_indices]
            final_embeddings = [final_embeddings[i] for i in valid_indices]
            distributions = [distributions[i] for i in valid_indices]  # Filter distributions as well

        if not field_names:
            logger.error("No embeddings available after retrieval and generation attempts.")
            return SimilarityMatrix(fields=[], scores=[])

        embeddings_array = np.array(final_embeddings)

        # Calculate cosine similarity
        similarity_matrix = np.zeros((len(field_names), len(field_names)))

        for i in range(len(field_names)):
            for j in range(len(field_names)):
                # Compute cosine similarity between embeddings
                dot_product = np.dot(embeddings_array[i], embeddings_array[j])
                norm_i = np.linalg.norm(embeddings_array[i])
                norm_j = np.linalg.norm(embeddings_array[j])

                if norm_i > 0 and norm_j > 0:
                    similarity_matrix[i, j] = dot_product / (norm_i * norm_j)
                else:
                    similarity_matrix[i, j] = 0

        # If including field values, adjust similarity scores
        if include_field_values and distributions:  # Check distributions is not empty
            for i, dist_i in enumerate(distributions):
                for j, dist_j in enumerate(distributions):
                    if i == j:
                        continue

                    # Adjust similarity based on field type
                    if dist_i.field_type == dist_j.field_type:
                        similarity_matrix[i, j] *= 1.2  # Boost similarity for same field type
                        similarity_matrix[i, j] = min(similarity_matrix[i, j], 1.0)  # Cap at 1.0

                    # Further adjust for categorical fields with shared values
                    if dist_i.field_type == FieldType.CATEGORICAL and dist_j.field_type == FieldType.CATEGORICAL:

                        values_i = set(v[0] for v in dist_i.top_values)
                        values_j = set(v[0] for v in dist_j.top_values)

                        if values_i and values_j:
                            # Calculate Jaccard similarity of value sets
                            jaccard = len(values_i.intersection(values_j)) / len(values_i.union(values_j))
                            # Weighted average of embedding and value similarity
                            similarity_matrix[i, j] = 0.7 * similarity_matrix[i, j] + 0.3 * jaccard

        return SimilarityMatrix(
            fields=field_names, scores=similarity_matrix.tolist(), timestamp=datetime.now(timezone.utc)
        )

    except Exception as e:
        logger.error(f"Error generating field similarity matrix: {str(e)}")
        return SimilarityMatrix(fields=[], scores=[])


async def invalidate_field_embeddings() -> int:
    """Deletes all stored field embeddings using the service."""
    try:
        deleted_count = await delete_all_field_embeddings()
        logger.info(f"Invalidated and deleted {deleted_count} field embeddings.")
        return deleted_count
    except Exception as e:
        logger.error(f"Error invalidating field embeddings: {e}")
        return -1  # Indicate error


async def get_field_embeddings_umap(
    min_occurrence: int = DEFAULT_MIN_OCCURRENCE,
    n_neighbors: int = 15,
    min_dist: float = 0.1,
    n_components: int = 3,  # Default to 3D
    metric: str = "cosine",
) -> Dict[str, Any]:
    """
    Generate UMAP projection of field embeddings.

    Args:
        min_occurrence: Minimum occurrences for a field to be included.
        n_neighbors: UMAP parameter: number of neighboring points used.
        min_dist: UMAP parameter: minimum distance between points.
        n_components: UMAP parameter: dimension of the embedded space (2 or 3).
        metric: UMAP parameter: distance metric used.

    Returns:
        Dictionary containing UMAP coordinates and field metadata.
    """
    if n_components not in [2, 3]:
        raise ValueError("n_components must be 2 or 3")

    try:
        # Get field distributions to have metadata
        distributions = await get_field_distribution(min_occurrence=min_occurrence, include_values=False)

        if not distributions:
            logger.warning("No fields found meeting criteria for UMAP projection")
            return {"fields": [], "umap_params": {}}

        field_names = [dist.field_name for dist in distributions]

        # Get existing embeddings from DB
        existing_embeddings = await get_field_embeddings(field_names)
        logger.info(f"UMAP: Found {len(existing_embeddings)} existing embeddings for {len(field_names)} fields.")

        # Identify fields needing new embeddings
        missing_fields = [name for name in field_names if name not in existing_embeddings]
        new_embeddings = {}

        if missing_fields:
            logger.info(f"UMAP: Generating embeddings for {len(missing_fields)} missing fields.")
            try:
                generated_embeddings = await embeddings_provider.get_embeddings(missing_fields)
                if generated_embeddings and len(generated_embeddings) == len(missing_fields):
                    new_embeddings = dict(zip(missing_fields, generated_embeddings))
                    logger.info(f"UMAP: Successfully generated {len(new_embeddings)} new embeddings.")

                    # Save new embeddings to DB
                    for field_name, embedding in new_embeddings.items():
                        await save_field_embedding(
                            field_name=field_name,
                            embedding=embedding,
                            provider=embeddings_provider.provider,
                            model=embeddings_provider.default_model,
                        )
                    logger.info(f"UMAP: Saved {len(new_embeddings)} new embeddings to the database.")
                else:
                    logger.error(
                        f"UMAP: Embedding generation failed or returned incorrect number of embeddings for {len(missing_fields)} fields."
                    )
            except Exception as e:
                logger.error(f"UMAP: Error generating or saving embeddings for missing fields: {e}", exc_info=True)

        # Combine existing and new embeddings
        all_embeddings_dict = {**existing_embeddings, **new_embeddings}

        # Ensure we have embeddings for all requested field names in the correct order
        final_embeddings = [all_embeddings_dict.get(name) for name in field_names]

        # Filter out fields for which we couldn't get embeddings
        valid_indices = [i for i, emb in enumerate(final_embeddings) if emb is not None]
        if len(valid_indices) < len(field_names):
            logger.warning(
                f"UMAP: Could not retrieve or generate embeddings for {len(field_names) - len(valid_indices)} fields. Proceeding with available embeddings."
            )
            field_names = [field_names[i] for i in valid_indices]
            final_embeddings = [final_embeddings[i] for i in valid_indices]
            distributions = [distributions[i] for i in valid_indices]  # Filter distributions as well

        if not field_names:
            logger.error("UMAP: No embeddings available after retrieval and generation attempts.")
            return {"fields": [], "umap_params": {}}

        embeddings_array = np.array(final_embeddings)

        # Perform UMAP reduction
        logger.info(f"Performing UMAP reduction on {len(embeddings_array)} embeddings to {n_components}D")
        reducer = umap.UMAP(
            n_neighbors=n_neighbors,
            min_dist=min_dist,
            n_components=n_components,
            metric=metric,
            random_state=42,
        )
        umap_result = reducer.fit_transform(embeddings_array)

        # Prepare result
        result_fields = []
        for i, dist in enumerate(distributions):
            result_fields.append(
                {
                    "name": dist.field_name,
                    "type": dist.field_type.value,
                    "count": dist.occurrence_count,
                    # Add type ignore for potential linter issue with umap result indexing
                    "coordinates": umap_result[i].tolist(),  # type: ignore
                }
            )

        return {
            "fields": result_fields,
            "umap_params": {
                "n_neighbors": n_neighbors,
                "min_dist": min_dist,
                "n_components": n_components,
                "metric": metric,
            },
        }

    except Exception as e:
        logger.error(f"Error generating UMAP projection: {str(e)}", exc_info=True)
        return {"fields": [], "umap_params": {}}


async def apply_active_mappings_retroactively(batch_size: int = 500) -> Dict[str, Any]:
    """
    Apply all currently active field mappings to all existing analyzed listings.
    This is useful after activating new mappings or updating existing ones.

    Args:
        batch_size: Number of listings to process in each batch.

    Returns:
        Dictionary with statistics about the operation.
    """
    logger.info("Starting retroactive application of active field mappings.")
    try:
        # 1. Get all active mappings and build a consolidated map
        active_mappings = await get_active_mappings()
        if not active_mappings:
            logger.info("No active mappings found. Retroactive application skipped.")
            return {"status": "success", "message": "No active mappings to apply", "documents_affected": 0}

        consolidated_map: Dict[str, str] = {}
        mapping_id_map: Dict[str, str] = {}  # Map original field to the mapping ID that defines its rule
        target_fields_in_use = set()
        for mapping in active_mappings:
            for field_map in mapping.mappings:
                # Ensure target field uniqueness constraint holds (should already be enforced, but double-check)
                if field_map.target_field in target_fields_in_use:
                    logger.warning(
                        f"Target field conflict detected during retroactive apply: {field_map.target_field}. Skipping rule {field_map.original_field} -> {field_map.target_field} from mapping {mapping.id}"
                    )
                    continue
                target_fields_in_use.add(field_map.target_field)

                # Only add if original != target
                if field_map.original_field != field_map.target_field:
                    consolidated_map[field_map.original_field] = field_map.target_field
                    mapping_id_map[field_map.original_field] = str(mapping.id)  # Store mapping ID

        if not consolidated_map:
            logger.info("No actual field transformations defined in active mappings.")
            return {"status": "success", "message": "No transformations to apply", "documents_affected": 0}

        logger.info(f"Consolidated mapping for retroactive application: {consolidated_map}")

        # 2. Iterate through AnalyzedListings in batches
        collection = AnalyzedListingDocument.get_motor_collection()
        total_docs = await collection.count_documents({})
        processed_count = 0
        updated_count = 0
        mappings_updated: Dict[str, Set[str]] = defaultdict(set)  # mapping_id -> set(listing_original_id)

        cursor = collection.find({})  # Find all documents

        async for doc in cursor:
            doc_id = doc["_id"]
            listing_original_id = doc.get("original_listing_id")
            if not listing_original_id:
                logger.warning(f"Skipping analyzed document {doc_id} due to missing original_listing_id")
                continue

            info = doc.get("info", {})
            if not info:
                continue  # Skip docs with no info

            transformed_info = info.copy()
            doc_changed = False
            affected_by_mappings = set()  # Mapping IDs that affected this specific doc
            fields_to_remove = []  # Track original fields to remove

            # Apply consolidated mappings
            for original_field, target_field in consolidated_map.items():
                if original_field in info:
                    original_value = info[original_field]
                    # Apply only if target doesn't exist or is empty
                    if target_field not in transformed_info or not transformed_info[target_field]:
                        transformed_info[target_field] = original_value
                        # Add original field to the removal list
                        fields_to_remove.append(original_field)
                        doc_changed = True
                        # Record which mapping ID was responsible
                        if original_field in mapping_id_map:
                            affected_by_mappings.add(mapping_id_map[original_field])

            # Remove the original fields after mapping
            for field in fields_to_remove:
                if field in transformed_info:
                    del transformed_info[field]

            # If changes were made, update the document
            if doc_changed:
                update_result = await collection.update_one({"_id": doc_id}, {"$set": {"info": transformed_info}})
                if update_result.modified_count > 0:
                    updated_count += 1
                    # Record which listings were affected by which mappings
                    for mapping_id in affected_by_mappings:
                        mappings_updated[mapping_id].add(listing_original_id)

            processed_count += 1
            if processed_count % batch_size == 0:
                logger.info(f"Retroactively processed {processed_count}/{total_docs} analyzed listings.")

        logger.info(f"Finished processing analyzed listings. {updated_count} documents updated.")

        # 3. Update affected_listings in FieldHarmonizationMapping documents
        mapping_collection = FieldHarmonizationMapping.get_motor_collection()
        if mappings_updated:
            logger.info(f"Updating affected_listings for {len(mappings_updated)} mappings.")
            bulk_mapping_updates = []
            for mapping_id_str, listing_ids in mappings_updated.items():
                # Convert mapping_id string back to ObjectId if necessary, depends on how it was stored
                # Assuming mapping_id_map stored string representation of PydanticObjectId
                from bson import ObjectId  # Import ObjectId if needed

                try:
                    mapping_oid = ObjectId(mapping_id_str)
                except Exception:
                    logger.error(f"Could not convert mapping ID {mapping_id_str} to ObjectId. Skipping update.")
                    continue

                bulk_mapping_updates.append(
                    UpdateOne({"_id": mapping_oid}, {"$addToSet": {"affected_listings": {"$each": list(listing_ids)}}})
                )

            if bulk_mapping_updates:
                await mapping_collection.bulk_write(bulk_mapping_updates)
                logger.info("Finished updating affected_listings sets.")

        return {
            "status": "success",
            "message": "Retroactive mapping application completed.",
            "total_documents_processed": processed_count,
            "documents_updated": updated_count,
            "mappings_involved": len(mappings_updated),
        }

    except Exception as e:
        logger.error(f"Error during retroactive mapping application: {str(e)}", exc_info=True)
        return {"error": f"Failed during retroactive application: {str(e)}"}
