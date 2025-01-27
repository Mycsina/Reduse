from datetime import datetime
from decimal import Decimal
from typing import Optional, Annotated

from beanie import Document
from pydantic import Field, field_validator
from bson import Decimal128


class ModelPriceStats(Document):
    """Price statistics for a specific model at a point in time."""

    timestamp: datetime = Field(default_factory=datetime.now)
    base_model: Annotated[str, Field(index=True)]  # type: ignore
    avg_price: Decimal
    min_price: Decimal
    max_price: Decimal
    median_price: Decimal
    sample_size: int  # Number of listings used for calculation

    @field_validator("avg_price", "min_price", "max_price", "median_price", mode="before")
    @classmethod
    def convert_decimal(cls, v: Optional[Decimal128]) -> Optional[Decimal]:
        if isinstance(v, Decimal128):
            return Decimal(str(v))
        return v

    class Settings:
        name = "model_price_stats"
        timeseries = {"time_field": "timestamp", "granularity": "hours", "meta_field": "base_model"}
        indexes = [[("base_model", 1), ("timestamp", -1)]]  # For efficient time-series queries per model
