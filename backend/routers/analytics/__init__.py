"""Analytics API endpoints module."""

from fastapi import APIRouter, Depends

from backend.routers.analytics.price_stats import router as price_stats_router
from backend.security import verify_security

router = APIRouter(prefix="/analytics")

router.include_router(price_stats_router)

__all__ = ["router"]
