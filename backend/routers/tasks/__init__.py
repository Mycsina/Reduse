"""Query endpoints."""

from fastapi import APIRouter

from .functions import router as functions_router
from .schedule import router as schedule_router

router = APIRouter(prefix="/tasks")
router.include_router(functions_router)
router.include_router(schedule_router)

__all__ = ["router"]
