"""Admin routes module."""

from fastapi import APIRouter

from . import analytics, analysis, scrape

# Create router
router = APIRouter()

# Include admin routes
router.include_router(analytics.router, prefix="/analytics", tags=["admin-analytics"])
router.include_router(analysis.router, prefix="/analysis", tags=["admin-analysis"])
router.include_router(scrape.router, prefix="/scrape", tags=["admin-scrape"])
