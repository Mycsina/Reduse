"""Admin routes module."""

from fastapi import APIRouter, Depends

from backend.routers.admin import analysis, field_harmonization, scrape, tasks
from backend.security import verify_security_admin

router = APIRouter(prefix="/admin", dependencies=[Depends(verify_security_admin)])

router.include_router(analysis.router, prefix="/analysis", tags=["admin-analysis"])
router.include_router(scrape.router, prefix="/scrape", tags=["admin-scrape"])
router.include_router(field_harmonization.router, prefix="/field-harmonization", tags=["admin-field-harmonization"])
router.include_router(tasks.router, prefix="/tasks", tags=["admin-tasks"])
