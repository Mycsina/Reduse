from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from beanie import Document
from bson import Decimal128
from bson import ObjectId as BaseObjectId
from bson.errors import InvalidId
from pydantic import Field, field_validator
from pydantic_core import core_schema
from pydantic_core.core_schema import ValidationInfo


class ObjectId(BaseObjectId):
    """Custom ObjectId class with a custom JSON encoder."""

    @classmethod
    def validate(cls, value: Any, info: ValidationInfo) -> "ObjectId":
        if isinstance(value, BaseObjectId):
            return cls(str(value))
        elif isinstance(value, str):
            try:
                return cls(value)
            except InvalidId:
                raise ValueError("Not a valid ObjectId")
        elif isinstance(value, bytes):
            try:
                return cls(value)
            except InvalidId:
                raise ValueError("Not a valid ObjectId")
        raise ValueError("Not a valid ObjectId")

    def __str__(self) -> str:
        return str(super().__str__())

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: Any
    ) -> core_schema.CoreSchema:
        return core_schema.with_info_plain_validator_function(cls.validate)


class MappingLog(Document):
    """Document for tracking field mapping changes."""

    mapping_id: ObjectId  # Reference to the FieldMapping that caused this change
    document_id: ObjectId  # Reference to the analyzed listing that was changed
    original_field: str  # Original field name
    mapped_field: str  # New field name after mapping
    original_value: Any  # Original value before mapping
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "mapping_logs"
        indexes = [
            [("mapping_id", 1)],  # For finding all changes from a mapping
            [("document_id", 1)],  # For finding all changes to a document
            [("timestamp", -1)],  # For historical queries
            [("original_field", 1), ("mapped_field", 1)],  # For field-based queries
        ]


class ModelPriceStats(Document):
    """Document for storing model price statistics."""

    base_model: str
    avg_price: Decimal
    min_price: Decimal
    max_price: Decimal
    median_price: Decimal
    sample_size: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    variants: List[str] = Field(
        default_factory=list,
        description="List of model variants included in this group",
    )

    @field_validator(
        "avg_price", "min_price", "max_price", "median_price", mode="before"
    )
    @classmethod
    def convert_decimal(cls, v: Optional[Decimal128]) -> Optional[Decimal]:
        if isinstance(v, Decimal128):
            return Decimal(str(v))
        return v

    class Settings:
        name = "model_price_stats"
        indexes = [
            [
                ("base_model", 1),
                ("timestamp", -1),
            ],  # Compound index for efficient querying
            [("timestamp", -1)],  # Index for sorting by timestamp
        ]


class FieldValueStats(Document):
    """Document for storing statistics about field values."""

    field_name: str  # Name of the field
    value_type: str  # Type of the values: numeric, categorical, boolean, mixed, unknown
    common_values: List[Tuple[str, int]]  # List of (value, count) tuples
    total_occurrences: int  # Total number of occurrences of this field
    distinct_values: int  # Number of distinct values for this field
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "field_value_stats"
        indexes = [
            [("field_name", 1)],  # For finding statistics for a specific field
            [("value_type", 1)],  # For grouping fields by type
            [("total_occurrences", -1)],  # For sorting by popularity
            [("last_updated", -1)],  # For finding recently updated stats
        ]


class FieldMapping(Document):
    """Document for storing field mappings."""

    mappings: Dict[str, str]  # Maps original field names to their canonical forms
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True  # Flag to mark the current active mapping set

    class Settings:
        name = "field_mappings"
        indexes = [
            [("is_active", 1)],  # For finding active mapping set
            [("created_at", -1)],  # For historical tracking
        ]
