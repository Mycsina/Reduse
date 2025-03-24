"""Admin routes for analysis operations."""

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel

from ...logic import analysis
from ...security import verify_api_key

router = APIRouter()


class AnalysisStatusResponse(BaseModel):
    message: str
    total: Optional[int] = None
    completed: Optional[int] = None
    pending: Optional[int] = None
    failed: Optional[int] = None
    in_progress: Optional[int] = None
    max_retries_reached: Optional[int] = None


class CancelAnalysisResponse(BaseModel):
    message: str
    cancelled: int


@router.get("/status")
async def get_analysis_status(_: str = Depends(verify_api_key)):
    """Get the current status of analysis tasks."""
    return await analysis.get_analysis_status()


@router.post("/retry-failed", response_model=AnalysisStatusResponse)
async def retry_failed_analyses(background_tasks: BackgroundTasks, _: str = Depends(verify_api_key)):
    """Retry all failed analyses."""
    status = await analysis.get_analysis_status()
    if status.failed == 0:
        return AnalysisStatusResponse(message="No failed analyses to retry", **status.model_dump())

    background_tasks.add_task(analysis.retry_failed_analyses)
    return AnalysisStatusResponse(message=f"Retrying {status.failed} failed analyses", **status.model_dump())


@router.post("/start", response_model=AnalysisStatusResponse)
async def start_analysis(background_tasks: BackgroundTasks, _: str = Depends(verify_api_key)):
    """Start analysis for unprocessed listings."""
    status = await analysis.get_analysis_status()

    if status.pending == 0:
        return AnalysisStatusResponse(message="No pending analyses to start", **status.model_dump())

    background_tasks.add_task(analysis.analyze_new_listings)
    return AnalysisStatusResponse(
        message=f"Started processing {status.pending + status.failed} unanalyzed listings", **status.model_dump()
    )


@router.post("/resume", response_model=AnalysisStatusResponse)
async def resume_analysis(background_tasks: BackgroundTasks, _: str = Depends(verify_api_key)):
    """Resume all in-progress analyses."""
    status = await analysis.get_analysis_status()

    if status.in_progress == 0:
        return AnalysisStatusResponse(message="No in-progress analyses to resume", **status.model_dump())

    background_tasks.add_task(analysis.resume_analysis)
    return AnalysisStatusResponse(message=f"Resuming {status.in_progress} in-progress analyses", **status.model_dump())


@router.post("/cancel", response_model=CancelAnalysisResponse)
async def cancel_analysis(_: str = Depends(verify_api_key)):
    """Cancel all pending analyses."""
    cancelled = await analysis.cancel_in_progress()
    return CancelAnalysisResponse(message=f"Cancelled {cancelled} in-progress analyses", cancelled=cancelled)


@router.post("/regenerate-embeddings")
async def regenerate_embeddings(background_tasks: BackgroundTasks, _: str = Depends(verify_api_key)):
    """Regenerate embeddings for all analyzed listings."""
    background_tasks.add_task(analysis.regenerate_embeddings)
    return {"message": "Started regenerating embeddings for all listings"}
