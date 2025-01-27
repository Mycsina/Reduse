"""Analytics endpoints."""

from decimal import Decimal
from datetime import datetime
from typing import List, Optional

from bson import Decimal128
from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, field_validator

from ..security import verify_api_key
from ..services.analytics_service import get_model_price_history, update_model_price_stats
from ..utils.utils import _to_decimal


class ModelPriceStatsResponse(BaseModel):
    """Response model for model price statistics."""

    model: str
    avg_price: Decimal
    min_price: Decimal
    max_price: Decimal
    median_price: Decimal
    sample_size: int
    timestamp: datetime

    @field_validator("avg_price", "min_price", "max_price", "median_price", mode="before")
    @classmethod
    def validate_price(cls, value: Decimal128) -> Optional[Decimal]:
        """Validate price."""
        return _to_decimal(value)


router = APIRouter(prefix="/analytics")


@router.get("/current/{base_model}", response_model=Optional[ModelPriceStatsResponse])
async def get_current_model_stats(base_model: str):
    """Get current price statistics for a specific model."""
    stats = await get_model_price_history(base_model=base_model, days=1, limit=1)
    return stats[0] if stats else None


@router.get("/history/{base_model}", response_model=List[ModelPriceStatsResponse])
async def get_model_stats_history(
    base_model: str,
    days: int = 30,
    limit: Optional[int] = None,
):
    """Get price statistics history for a specific model."""
    return await get_model_price_history(base_model=base_model, days=days, limit=limit)


@router.post("/update-stats")
async def update_price_stats(
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_api_key),
):
    """Create new price statistics for all models."""
    background_tasks.add_task(update_model_price_stats)
    return {"message": "Started updating price statistics"}
