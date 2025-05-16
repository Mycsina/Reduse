"""Field harmonization API endpoints for managing field mappings."""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from backend.schemas.field_harmonization import (
    CreateMappingRequest,
    FieldCluster,
    FieldDistribution,
    FieldHarmonizationMapping,
    FieldMapping,
    FieldMappingImpact,
    HarmonizationSuggestion,
    SimilarityMatrix,
    SuggestFieldMappingsRequest,
    UpdateMappingRequest,
)
from backend.services.analytics.field_harmonization import (
    apply_active_mappings_retroactively,
    create_field_mapping,
    delete_field_mapping,
    generate_field_similarity_matrix,
    get_active_mappings,
    get_field_distribution,
    get_field_embeddings_umap,
    get_field_mapping_history,
    get_field_mapping_impact,
    invalidate_field_embeddings,
    suggest_field_mappings,
    update_field_mapping,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/distribution", response_model=List[FieldDistribution])
async def get_field_distributions(
    min_occurrence: int = 5,
    include_values: bool = True,
    top_values_limit: int = 10,
):
    """Get distribution statistics for fields."""
    return await get_field_distribution(
        min_occurrence=min_occurrence,
        include_values=include_values,
        top_values_limit=top_values_limit,
    )


@router.get("/similarity-matrix", response_model=SimilarityMatrix)
async def get_similarity_matrix(
    min_occurrence: int = 5,
    include_field_values: bool = True,
):
    """Generate a similarity matrix for fields."""
    return await generate_field_similarity_matrix(
        min_occurrence=min_occurrence,
        include_field_values=include_field_values,
    )


@router.post("/suggest-mappings", response_model=HarmonizationSuggestion)
async def suggest_mappings(
    request: SuggestFieldMappingsRequest,
):
    """Suggest field mappings based on similarity."""
    return await suggest_field_mappings(
        similarity_threshold=request.similarity_threshold,
        min_occurrence=request.min_occurrence,
        protected_fields=request.protected_fields,
    )


@router.get("/mappings", response_model=List[FieldHarmonizationMapping])
async def get_mappings(
    days: int = 30,
):
    """Get field mapping history."""
    return await get_field_mapping_history(days=days)


@router.get("/mappings/active", response_model=List[FieldHarmonizationMapping])
async def get_active_mapping():
    """Get all active field mappings."""
    return await get_active_mappings()


@router.post("/mappings/impact", response_model=FieldMappingImpact)
async def calculate_mapping_impact(
    field_mapping: Dict[str, str],
):
    """Calculate the impact of applying a field mapping."""
    if not field_mapping:
        raise HTTPException(status_code=400, detail="Field mapping cannot be empty")

    return await get_field_mapping_impact(field_mapping)


@router.get("/embeddings/umap", response_model=Dict[str, Any])
async def get_embeddings_umap(
    min_occurrence: int = Query(5, description="Minimum occurrences for a field to be included"),
    n_neighbors: int = Query(15, description="UMAP: Number of neighbors"),
    min_dist: float = Query(0.1, description="UMAP: Minimum distance"),
    n_components: int = Query(3, description="UMAP: Number of dimensions (2 or 3)", ge=2, le=3),
    metric: str = Query("cosine", description="UMAP: Distance metric"),
):
    """Generate UMAP projection of field embeddings."""
    result = await get_field_embeddings_umap(
        min_occurrence=min_occurrence,
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        n_components=n_components,
        metric=metric,
    )
    if not result or not result.get("fields"):
        raise HTTPException(status_code=500, detail="Failed to generate UMAP projection")
    return result


@router.post("/embeddings/invalidate", status_code=200, response_model=Dict[str, Any])
async def invalidate_embeddings():
    """Invalidate and delete all stored field embeddings."""
    deleted_count = await invalidate_field_embeddings()
    if deleted_count < 0:
        raise HTTPException(status_code=500, detail="Failed to invalidate embeddings")
    return {"message": f"Successfully invalidated {deleted_count} embeddings."}


@router.post("/mappings", response_model=FieldHarmonizationMapping)
async def create_mapping(
    request: CreateMappingRequest,
):
    """Create a new field mapping."""
    mapping = await create_field_mapping(
        name=request.name,
        mappings=request.mappings,
        description=request.description,
        is_active=request.is_active,
        created_by=request.created_by,
    )

    if not mapping:
        raise HTTPException(status_code=500, detail="Failed to create field mapping")

    return mapping


@router.patch("/mappings/{mapping_id}", response_model=FieldHarmonizationMapping)
async def update_mapping(
    mapping_id: str,
    request: UpdateMappingRequest,
):
    """Update an existing field mapping."""
    mapping = await update_field_mapping(
        mapping_id=mapping_id,
        name=request.name,
        description=request.description,
        mappings_to_add=request.mappings_to_add,
        mappings_to_remove=request.mappings_to_remove,
        is_active=request.is_active,
    )

    if not mapping:
        raise HTTPException(status_code=404, detail=f"Mapping {mapping_id} not found")

    return mapping


@router.delete("/mappings/{mapping_id}", status_code=204)
async def delete_mapping_endpoint(
    mapping_id: str,
):
    """Delete a field harmonization mapping permanently."""
    success, message = await delete_field_mapping(mapping_id)

    if not success:
        # Determine the appropriate status code based on the message
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message)
        else:
            # Assume internal server error for other failures
            raise HTTPException(status_code=500, detail=message)

    # On success, return None and FastAPI will send a 204 response
    return None


@router.post("/mappings/apply-retroactive", response_model=Dict[str, Any])
async def apply_mappings_retroactively_endpoint(
    batch_size: int = Query(500, ge=100, le=5000, description="Number of listings to process per batch"),
):
    """Apply all active mappings to existing analyzed listings."""
    try:
        result = await apply_active_mappings_retroactively(batch_size=batch_size)
        if "error" in result:
            # Distinguish between client errors (e.g., conflicts) and server errors
            # For now, assume internal error
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except Exception as e:
        logger.error(f"Unhandled error during retroactive mapping application: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")
