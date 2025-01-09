from fastapi import APIRouter, BackgroundTasks, Depends

from ..logic import analysis
from ..security import verify_api_key

router = APIRouter(prefix="/analysis")


@router.get("/status")
async def get_analysis_status(api_key: str = Depends(verify_api_key)):
    """Get the current status of listing analysis."""
    status = await analysis.get_analysis_status()
    return status


@router.post("/retry-failed")
async def retry_failed_analyses(background_tasks: BackgroundTasks, api_key: str = Depends(verify_api_key)):
    """Retry failed analyses."""
    status = await analysis.get_analysis_status()

    if status["failed"] == 0:
        return {"message": "No failed analyses to retry.", "can_retry": False, **status}
    background_tasks.add_task(analysis.retry_failed_analyses)

    msg = f"Retrying analysis for {status['failed']} listings. "
    return {"message": msg}


@router.post("/start")
async def start_analysis(background_tasks: BackgroundTasks, api_key: str = Depends(verify_api_key)):
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
