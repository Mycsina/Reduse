"""Query endpoints."""

from fastapi import APIRouter

from .listings import router as listings_router

router = APIRouter(prefix="/query")
router.include_router(listings_router)

__all__ = ["router"]
