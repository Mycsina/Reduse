"""Analysis endpoints."""

from fastapi import APIRouter, BackgroundTasks, Depends

from ..logic import analysis
from ..security import verify_api_key

router = APIRouter(prefix="/analysis")


@router.get("/status")
async def get_analysis_status(_: str = Depends(verify_api_key)):
    """Get the current status of listing analysis."""
    status = await analysis.get_analysis_status()
    return status


@router.post("/retry-failed")
async def retry_failed_analyses(background_tasks: BackgroundTasks, _: str = Depends(verify_api_key)):
    """Retry failed analyses."""
    status = await analysis.get_analysis_status()

    if status["failed"] == 0:
        return {"message": "No failed analyses to retry.", "can_retry": False, **status}
    background_tasks.add_task(analysis.retry_failed_analyses)

    msg = f"Retrying analysis for {status['failed']} listings. "
    return {"message": msg}


@router.post("/start")
async def start_analysis(background_tasks: BackgroundTasks, _: str = Depends(verify_api_key)):
    """Start analysis of pending listings."""
    status = await analysis.get_analysis_status()

    if status["pending"] == 0:
        return {"message": "No pending listings to analyze.", "can_start": False, **status}

    if not status["can_process"]:
        return {
            "message": "Rate limits reached. Please try again later.",
            "can_start": False,
            **status,
        }

    background_tasks.add_task(
        analysis.analyze_new_listings,
    )
    return {
        "message": f"Starting analysis of {status['pending']} listings.",
        "can_start": True,
        **status,
    }


@router.post("/resume")
async def resume_analysis(background_tasks: BackgroundTasks, _: str = Depends(verify_api_key)):
    """Resume analysis of in progress listings."""
    status = await analysis.get_analysis_status()

    if status["in_progress"] == 0:
        return {"message": "No in-progress listings to resume.", "can_resume": False, **status}

    background_tasks.add_task(analysis.resume_analysis)
    return {"message": f"Resuming analysis of {status['in_progress']} listings.", "can_resume": True, **status}


@router.post("/reanalyze")
async def reanalyze_listings(background_tasks: BackgroundTasks, _: str = Depends(verify_api_key)):
    """Reanalyze all listings."""
    background_tasks.add_task(analysis.reanalyze_listings)
    return {"message": "Reanalyzing all listings."}


@router.post("/cancel")
async def cancel_analysis(_: str = Depends(verify_api_key)):
    """Cancel in-progress analysis tasks."""
    status = await analysis.get_analysis_status()

    if status["in_progress"] == 0:
        return {"message": "No analysis tasks in progress.", "cancelled": 0}

    cancelled = await analysis.cancel_in_progress()
    return {"message": f"Cancelled {cancelled} in-progress analysis tasks.", "cancelled": cancelled}


@router.post("/regenerate-embeddings")
async def regenerate_embeddings(background_tasks: BackgroundTasks, _: str = Depends(verify_api_key)):
    """Regenerate embeddings for all completed analyses using the latest model."""
    background_tasks.add_task(analysis.regenerate_embeddings)
    return {"message": "Started regenerating embeddings for all completed analyses"}
