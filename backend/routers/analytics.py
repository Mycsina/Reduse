"""Analytics endpoints."""

import logging
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..schemas.analytics import ModelPriceStats
from ..services.analytics import (get_current_model_price_stats,
                                  get_model_price_history)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics")


@router.get("/current/{base_model}", response_model=Optional[ModelPriceStats])
async def get_current_model_stats(base_model: str) -> Optional[ModelPriceStats]:
    """Get current price statistics for a specific model."""
    if base_model == "null":
        return None
    result = await get_current_model_price_stats(base_model=base_model)
    if not result:
        logger.error(f"No price stats found for model: {base_model}")
        return None
    return result


@router.get("/history/{base_model}", response_model=List[ModelPriceStats])
async def get_model_stats_history(
    base_model: str,
    days: int = 30,
    limit: Optional[int] = None,
) -> List[ModelPriceStats]:
    """Get price statistics history for a specific model."""
    return await get_model_price_history(base_model=base_model, days=days, limit=limit)
