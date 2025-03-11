"""Admin routes for analytics operations."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from ...logic import analytics as analytics_logic
from ...services.analytics import update_model_price_stats
from ...security import verify_api_key

router = APIRouter()
logger = logging.getLogger(__name__)


class FieldMappingResponse(BaseModel):
    id: str
    mappings: Dict[str, str]
    created_at: datetime
    is_active: bool


class FuseFieldsRequest(BaseModel):
    """Request model for field fusion with enhanced options."""

    similarity_threshold: float = Field(
        default=0.9, ge=0.5, le=1.0, description="Similarity threshold for grouping fields"
    )
    dry_run: bool = Field(default=True, description="If true, only generate mapping without applying it")
    use_llm: bool = Field(default=True, description="Use LLM for ambiguous cases")
    min_occurrence: int = Field(default=5, ge=0, description="Minimum occurrences for a field to be considered")


class FuseFieldsResponse(BaseModel):
    """Response model for enhanced field fusion."""

    mapping: Dict[str, str] = Field(description="Field mapping dictionary")
    impact: Dict[str, Any] = Field(description="Impact report")
    warnings: List[str] = Field(default_factory=list, description="Warnings during mapping")
    execution_time_seconds: float = Field(description="Time taken to execute the operation")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")


class UpdateStatsResponse(BaseModel):
    """Response model for update stats endpoint."""
    message: str


@router.post("/fields/fuse", response_model=FuseFieldsResponse)
async def fuse_info_fields(request: FuseFieldsRequest):
    """Fuse semantically similar fields using enhanced algorithms.

    This endpoint:
    1. Collects all unique field names
    2. Uses embeddings and clustering to group similar fields
    3. Uses field value context and optional LLM assistance to resolve ambiguities
    4. Validates the mapping against protected fields and existing mappings
    5. Applies the mapping (if not dry run)

    Returns a detailed report of the proposed mappings and their impact.
    """
    try:
        logger.info(
            f"Fusing info fields with threshold={request.similarity_threshold}, "
            f"dry_run={request.dry_run}, use_llm={request.use_llm}, "
            f"min_occurrence={request.min_occurrence}"
        )

        result = await analytics_logic.fuse_info_fields(
            similarity_threshold=request.similarity_threshold,
            dry_run=request.dry_run,
            use_llm=request.use_llm,
            min_occurrence=request.min_occurrence,
        )

        return FuseFieldsResponse(
            mapping=result.get("mapping", {}),
            impact=result.get("impact", {}),
            warnings=result.get("warnings", []),
            execution_time_seconds=result.get("execution_time_seconds", 0.0),
            error=result.get("error"),
        )

    except Exception as e:
        logger.error(f"Error in fuse_info_fields endpoint: {str(e)}")
        return FuseFieldsResponse(mapping={}, impact={}, warnings=[], execution_time_seconds=0.0, error=str(e))


@router.get("/fields/mappings", response_model=List[FieldMappingResponse])
async def get_field_mappings(days: int = 30):
    """Get field mapping history for the specified time period."""
    mappings = await analytics_logic.get_field_mappings(days)
    return [
        FieldMappingResponse(
            id=str(mapping.id),
            mappings=mapping.mappings,
            created_at=mapping.created_at,
            is_active=mapping.is_active,
        )
        for mapping in mappings
    ]


@router.get("/fields/current-mapping", response_model=Optional[FieldMappingResponse])
async def get_current_mapping():
    """Get the currently active field mapping."""
    mapping = await analytics_logic.get_current_field_mapping()
    if not mapping:
        return None

    return FieldMappingResponse(
        id=str(mapping.id),
        mappings=mapping.mappings,
        created_at=mapping.created_at,
        is_active=mapping.is_active,
    )


@router.post("/fields/revert")
async def revert_field_mappings(mapping_ids: List[str], dry_run: bool = True):
    """Revert the effects of field mappings."""
    return await analytics_logic.revert_mappings(mapping_ids, dry_run)


@router.post("/update-stats", response_model=UpdateStatsResponse)
async def update_price_stats(
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_api_key),
):
    """Create new price statistics for all models."""
    background_tasks.add_task(update_model_price_stats)
    return UpdateStatsResponse(message="Started updating price statistics")
