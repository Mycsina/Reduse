"""Analysis endpoints."""

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from ..logic import analysis
from ..schemas.analysis import AnalysisStats, AnalyzedListingDocument
from ..security import verify_api_key
from ..services.query import get_analysis_by_original_id

router = APIRouter(prefix="/analysis")


class AnalysisStatusResponse(BaseModel):
    message: str
    can_retry: Optional[bool] = None
    can_start: Optional[bool] = None
    can_resume: Optional[bool] = None
    total: Optional[int] = None
    completed: Optional[int] = None
    pending: Optional[int] = None
    failed: Optional[int] = None
    in_progress: Optional[int] = None
    max_retries_reached: Optional[int] = None


class CancelAnalysisResponse(BaseModel):
    message: str
    cancelled: int


@router.get("/status", response_model=AnalysisStats)
async def get_analysis_status(_: str = Depends(verify_api_key)):
    """Get the current status of listing analysis."""
    status = await analysis.get_analysis_status()
    return status


@router.post("/retry-failed", response_model=AnalysisStatusResponse)
async def retry_failed_analyses(
    background_tasks: BackgroundTasks, _: str = Depends(verify_api_key)
):
    """Retry failed analyses."""
    status = await analysis.get_analysis_status()

    if status.failed == 0:
        return AnalysisStatusResponse(
            message="No failed analyses to retry.",
            can_retry=False,
            total=status.total,
            completed=status.completed,
            pending=status.pending,
            failed=status.failed,
            in_progress=status.in_progress,
            max_retries_reached=status.max_retries_reached,
        )
    background_tasks.add_task(analysis.retry_failed_analyses)

    msg = f"Retrying analysis for {status.failed} listings. "
    return AnalysisStatusResponse(
        message=msg,
        total=status.total,
        completed=status.completed,
        pending=status.pending,
        failed=status.failed,
        in_progress=status.in_progress,
        max_retries_reached=status.max_retries_reached,
    )


@router.post("/start", response_model=AnalysisStatusResponse)
async def start_analysis(
    background_tasks: BackgroundTasks, _: str = Depends(verify_api_key)
):
    """Start analysis of pending listings."""
    status = await analysis.get_analysis_status()

    if status.pending == 0:
        return AnalysisStatusResponse(
            message="No pending listings to analyze.",
            can_start=False,
            total=status.total,
            completed=status.completed,
            pending=status.pending,
            failed=status.failed,
            in_progress=status.in_progress,
            max_retries_reached=status.max_retries_reached,
        )

    if not status.can_process:
        return AnalysisStatusResponse(
            message="Rate limits reached. Please try again later.",
            can_start=False,
            total=status.total,
            completed=status.completed,
            pending=status.pending,
            failed=status.failed,
            in_progress=status.in_progress,
            max_retries_reached=status.max_retries_reached,
        )

    background_tasks.add_task(
        analysis.analyze_new_listings,
    )
    return AnalysisStatusResponse(
        message=f"Starting analysis of {status.pending} listings.",
        can_start=True,
        total=status.total,
        completed=status.completed,
        pending=status.pending,
        failed=status.failed,
        in_progress=status.in_progress,
        max_retries_reached=status.max_retries_reached,
    )


@router.post("/resume", response_model=AnalysisStatusResponse)
async def resume_analysis(
    background_tasks: BackgroundTasks, _: str = Depends(verify_api_key)
):
    """Resume analysis of in progress listings."""
    status = await analysis.get_analysis_status()

    if status.in_progress == 0:
        return AnalysisStatusResponse(
            message="No in-progress listings to resume.",
            can_resume=False,
            total=status.total,
            completed=status.completed,
            pending=status.pending,
            failed=status.failed,
            in_progress=status.in_progress,
            max_retries_reached=status.max_retries_reached,
        )

    background_tasks.add_task(analysis.resume_analysis)
    return AnalysisStatusResponse(
        message=f"Resuming analysis of {status.in_progress} listings.",
        can_resume=True,
        total=status.total,
        completed=status.completed,
        pending=status.pending,
        failed=status.failed,
        in_progress=status.in_progress,
        max_retries_reached=status.max_retries_reached,
    )


@router.post("/reanalyze")
async def reanalyze_listings(
    background_tasks: BackgroundTasks, _: str = Depends(verify_api_key)
):
    """Reanalyze all listings."""
    background_tasks.add_task(analysis.reanalyze_listings)
    return {"message": "Reanalyzing all listings."}


@router.post("/cancel", response_model=CancelAnalysisResponse)
async def cancel_analysis(_: str = Depends(verify_api_key)):
    """Cancel in-progress analysis tasks."""
    status = await analysis.get_analysis_status()

    if status.in_progress == 0:
        return CancelAnalysisResponse(
            message="No analysis tasks in progress.", cancelled=0
        )

    cancelled = await analysis.cancel_in_progress()
    return CancelAnalysisResponse(
        message=f"Cancelled {cancelled} in-progress analysis tasks.",
        cancelled=cancelled,
    )


@router.post("/regenerate-embeddings")
async def regenerate_embeddings(
    background_tasks: BackgroundTasks, _: str = Depends(verify_api_key)
):
    """Regenerate embeddings for all completed analyses using the latest model."""
    background_tasks.add_task(analysis.regenerate_embeddings)
    return {"message": "Started regenerating embeddings for all completed analyses"}


@router.get("/by-original-id/{original_id}", response_model=AnalyzedListingDocument)
async def get_analysis_by_original_id_route(
    original_id: str, _: str = Depends(verify_api_key)
):
    """Get analysis data for a listing by its original ID."""
    analysis_data = await get_analysis_by_original_id(original_id)
    if not analysis_data:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis_data
