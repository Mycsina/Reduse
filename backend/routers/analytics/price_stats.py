"""Price statistics API endpoints for model price analytics."""

import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks

from backend.schemas.analytics import ModelPriceStats
from backend.services.analytics.price_stats import (
    get_current_model_price_stats,
    get_model_price_history,
    update_model_price_stats,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/price-stats", tags=["price-stats"])


@router.get("/current/{base_model}", response_model=Optional[ModelPriceStats])
async def get_current_stats(base_model: str):
    """Get current price statistics for a specific model."""
    if not base_model or base_model == "null":
        return None

    result = await get_current_model_price_stats(base_model=base_model)
    if not result:
        logger.warning(f"No price stats found for model: {base_model}")

    return result


@router.get("/history/{base_model}", response_model=List[ModelPriceStats])
async def get_stats_history(
    base_model: str,
    days: int = 30,
    limit: Optional[int] = None,
):
    """Get price statistics history for a specific model."""
    if not base_model or base_model == "null":
        return []

    return await get_model_price_history(base_model=base_model, days=days, limit=limit)


@router.post("/update")
async def update_stats(
    background_tasks: BackgroundTasks,
):
    """Create new price statistics for all models."""
    background_tasks.add_task(update_model_price_stats)
    return {"message": "Started updating price statistics"}
