"""Schemas for field harmonization and field similarity analysis."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from beanie import Document
from beanie.odm.fields import PydanticObjectId
from pydantic import BaseModel, Field


class FieldType(str, Enum):
    """Type classification for product characteristic fields."""

    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"
    TEXT = "text"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class FieldValuePattern(BaseModel):
    """Pattern information detected in field values."""

    type: FieldType
    unit: Optional[str] = None
    distinct_values: Optional[int] = None
    value_examples: List[str] = Field(default_factory=list)
    stats: Optional[Dict[str, Any]] = None


class FieldCluster(BaseModel):
    """Group of semantically similar fields."""

    id: str = Field(description="Unique identifier for the cluster")
    canonical_field: str = Field(
        description="The canonical field name for this cluster"
    )
    similar_fields: List[str] = Field(
        default_factory=list,
        description="Fields that are similar to the canonical field",
    )
    field_types: Dict[str, FieldType] = Field(
        default_factory=dict, description="Type of each field in the cluster"
    )
    similarity_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="Similarity scores between canonical and each field",
    )
    patterns: Dict[str, FieldValuePattern] = Field(
        default_factory=dict, description="Value patterns for each field"
    )
    suggested_name: Optional[str] = Field(
        default=None, description="AI-suggested better name for the cluster"
    )


class FieldMapping(BaseModel):
    """Direct mapping from an original field to a target field."""

    original_field: str = Field(description="Original field name in the data")
    target_field: str = Field(description="Target/canonical field name")


class FieldHarmonizationMapping(Document):
    """Document for storing field mappings with additional metadata."""

    name: str = Field(description="Human-readable name for this mapping set")
    description: Optional[str] = Field(
        default=None, description="Description of the mapping purpose"
    )
    mappings: List[FieldMapping] = Field(
        default_factory=list, description="List of field mappings"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
    created_by: Optional[str] = None
    affected_listings: Set[str] = Field(
        default_factory=set,
        description="Set of listing IDs that were affected by this mapping",
    )

    class Settings:
        name = "field_harmonization_mappings"
        indexes = [
            [("is_active", 1)],
            [("created_at", -1)],
        ]


class FieldDistribution(BaseModel):
    """Distribution statistics for a field."""

    field_name: str
    occurrence_count: int
    distinct_value_count: int
    top_values: List[Tuple[str, int]]  # (value, count) pairs
    field_type: FieldType
    pattern: Optional[FieldValuePattern] = None
    cluster_id: Optional[str] = None  # If this field belongs to a cluster


class SimilarityMatrix(BaseModel):
    """Matrix of similarity scores between fields."""

    fields: List[str]
    scores: List[List[float]]  # 2D matrix of similarity scores
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FieldMappingImpact(BaseModel):
    """Impact analysis of applying a field mapping."""

    total_fields: int
    total_mapped_fields: int
    total_affected_documents: int
    field_impacts: Dict[str, Dict[str, Any]]  # Details about each field mapping impact
    clusters: List[FieldCluster]
    before_after_samples: List[
        Dict[str, Any]
    ]  # Sample documents before and after mapping


class HarmonizationSuggestion(BaseModel):
    """Field harmonization suggestion."""

    clusters: List[FieldCluster]
    suggested_mapping: Dict[str, str]
    impact: FieldMappingImpact
    similarity_threshold: float
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Request/Response models for API endpoints


class GenerateSimilarityMatrixRequest(BaseModel):
    """Request to generate a similarity matrix for fields."""

    min_occurrence: int = Field(
        default=5, ge=1, description="Minimum occurrences for a field to be included"
    )
    fields_to_include: Optional[List[str]] = Field(
        default=None, description="Specific fields to include (if None, include all)"
    )
    fields_to_exclude: Optional[List[str]] = Field(
        default=None, description="Specific fields to exclude"
    )
    use_values: bool = Field(
        default=True,
        description="Whether to use field values in similarity calculation",
    )
    embedding_model: str = Field(
        default="multilingual", description="Model to use for text embeddings"
    )


class SuggestFieldMappingsRequest(BaseModel):
    """Request to suggest field mappings."""

    similarity_threshold: float = Field(
        default=0.75,
        ge=0.5,
        le=1.0,
        description="Minimum similarity score to consider fields similar",
    )
    min_occurrence: int = Field(
        default=5, ge=1, description="Minimum occurrences for a field to be included"
    )
    use_llm_refinement: bool = Field(
        default=True, description="Whether to use LLM to refine suggestions"
    )
    max_clusters: Optional[int] = Field(
        default=None, description="Maximum number of clusters to generate"
    )
    protected_fields: Optional[List[str]] = Field(
        default=None, description="Fields that should not be mapped to others"
    )


class CreateMappingRequest(BaseModel):
    """Request to create a new field mapping."""

    name: str
    description: Optional[str] = None
    mappings: List[FieldMapping]
    is_active: bool = True
    created_by: Optional[str] = None


class UpdateMappingRequest(BaseModel):
    """Request to update an existing mapping."""

    name: Optional[str] = None
    description: Optional[str] = None
    mappings_to_add: Optional[List[FieldMapping]] = None
    mappings_to_remove: Optional[List[str]] = None  # Original field names to remove
    is_active: Optional[bool] = None
