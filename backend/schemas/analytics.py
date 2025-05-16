from datetime import datetime
from typing import Any, List, Tuple

from beanie import Document
from bson import ObjectId as BaseObjectId
from bson.errors import InvalidId
from pydantic import Field
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


class ModelPriceStats(Document):
    """Document for storing model price statistics."""

    base_model: str
    avg_price: float
    min_price: float
    max_price: float
    median_price: float
    sample_size: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    variants: List[str] = Field(
        default_factory=list,
        description="List of model variants included in this group",
    )

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
