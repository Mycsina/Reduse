"""Scheduling endpoints for recurring tasks."""

# TODO typing

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from apscheduler.jobstores.base import JobLookupError
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl
from sse_starlette.sse import EventSourceResponse

from ...logic import analysis, scraping
from ...security import verify_api_key
from ...tasks.scheduler import TaskConfig, scheduler
from ...tasks.task_registry import JobLogFilter, JobStatus, registry

# Initialize logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schedule", tags=["scheduling"])


class ScheduleBase(BaseModel):
    """Base model for schedule configuration."""

    job_id: Optional[str] = Field(
        default=None,
        description="Optional job ID. If not provided, one will be generated.",
    )
    cron: Optional[str] = None  # Cron expression (e.g. "0 0 * * *" for daily at midnight)
    interval_seconds: Optional[int] = None  # Interval in seconds
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    enabled: bool = True  # Whether the job should start enabled
    max_instances: int = Field(default=1, ge=1, le=10)  # Maximum number of concurrent instances


class ScrapeSchedule(ScheduleBase):
    """Schedule configuration for URL-based scraping tasks."""

    urls: List[HttpUrl]  # Support multiple URLs
    analyze: bool = True  # Whether to analyze scraped listings
    generate_embeddings: bool = True  # Whether to generate embeddings


class OLXScrapeSchedule(ScheduleBase):
    """Schedule configuration for OLX category scraping tasks."""

    analyze: bool = True  # Whether to analyze scraped listings
    generate_embeddings: bool = True  # Whether to generate embeddings
    categories: Optional[List[str]] = None  # Optional list of specific categories to scrape, if None scrapes all


class AnalysisSchedule(ScheduleBase):
    """Schedule configuration for analysis tasks."""

    retry_failed: bool = False  # Whether to retry failed analyses
    reanalyze_all: bool = False  # Whether to reanalyze all listings
    regenerate_embeddings: bool = False  # Whether to regenerate embeddings


class MaintenanceSchedule(ScheduleBase):
    """Schedule configuration for maintenance tasks."""

    cleanup_old_logs: bool = True  # Whether to clean up old log files
    vacuum_database: bool = True  # Whether to run database vacuum
    update_indexes: bool = True  # Whether to update database indexes


# Response models
class ScheduleResponse(BaseModel):
    """Response model for scheduling endpoints."""

    message: str
    job_id: str
    config: Dict[str, Any]


class SimpleJobResponse(BaseModel):
    """Simple response for job operations."""

    message: str
    job_id: str


class JobListResponse(BaseModel):
    """Response model for job listing."""

    jobs: List[Dict[str, Any]]


def generate_job_id(prefix: str) -> str:
    """Generate a unique job ID with a meaningful prefix."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@router.post("/scrape", response_model=ScheduleResponse)
async def schedule_scraping(config: ScrapeSchedule, _: str = Depends(verify_api_key)):
    """Schedule recurring scraping tasks for one or more URLs."""
    try:
        # Generate job ID if not provided
        if not config.job_id:
            config.job_id = generate_job_id("scrape")

        # Create the scraping pipeline function
        async def scraping_pipeline():
            for url in config.urls:
                try:
                    logger.info(f"Starting scheduled scraping for {url}")
                    # Step 1: Scrape and save
                    listings = await scraping.scrape_and_save(str(url))
                    if not listings:
                        logger.warning(f"No listings found for {url}")
                        continue

                    if config.analyze:
                        # Step 2: Analyze listings
                        logger.info(f"Analyzing {len(listings)} listings from {url}")
                        await analysis.analyze_and_save(listings)

                except Exception as e:
                    logger.error(f"Error in scheduled scraping for {url}: {str(e)}")

        # Create task config
        task_config = TaskConfig(
            job_id=config.job_id,
            cron=config.cron,
            interval_seconds=config.interval_seconds,
            max_instances=config.max_instances,
            enabled=config.enabled,
        )

        # Register and schedule the task
        registry.register()(scraping_pipeline)
        job_id = await scheduler.schedule_function(scraping_pipeline.__name__, task_config)

        return ScheduleResponse(
            message=f"Scheduled scraping job {job_id}",
            job_id=job_id,
            config=config.dict(exclude={"job_id"}),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/scrape/olx", response_model=ScheduleResponse)
async def schedule_olx_scraping(config: OLXScrapeSchedule, _: str = Depends(verify_api_key)):
    """Schedule recurring OLX category scraping tasks."""
    try:
        # Generate job ID if not provided
        if not config.job_id:
            config.job_id = generate_job_id("olx_scrape")

        # Create the OLX scraping pipeline function
        async def olx_scraping_pipeline():
            try:
                logger.info("Starting scheduled OLX category scraping")

                # Step 1: Scrape OLX categories
                listings = await scraping.scrape_olx_categories()
                if not listings:
                    logger.warning("No listings found in OLX categories")
                    return

                if config.analyze:
                    # Step 2: Analyze listings
                    logger.info(f"Analyzing {len(listings)} listings from OLX")
                    await analysis.analyze_and_save(listings)

            except Exception as e:
                logger.error(f"Error in scheduled OLX scraping: {str(e)}")

        # Create task config
        task_config = TaskConfig(
            job_id=config.job_id,
            cron=config.cron,
            interval_seconds=config.interval_seconds,
            max_instances=config.max_instances,
            enabled=config.enabled,
        )

        # Register and schedule the task
        registry.register()(olx_scraping_pipeline)
        job_id = await scheduler.schedule_function(olx_scraping_pipeline.__name__, task_config)

        return ScheduleResponse(
            message=f"Scheduled OLX scraping job {config.job_id}",
            job_id=config.job_id,
            config=config.dict(exclude={"job_id"}),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/analysis", response_model=ScheduleResponse)
async def schedule_analysis(config: AnalysisSchedule, _: str = Depends(verify_api_key)):
    """Schedule recurring analysis tasks."""
    try:
        # Generate job ID if not provided
        if not config.job_id:
            config.job_id = generate_job_id("analysis")

        # Create the analysis pipeline function
        async def analysis_pipeline():
            try:
                if config.reanalyze_all:
                    await analysis.reanalyze_listings()
                elif config.retry_failed:
                    await analysis.retry_failed_analyses()
                else:
                    await analysis.analyze_new_listings()

                if config.regenerate_embeddings:
                    await analysis.regenerate_embeddings()

            except Exception as e:
                logger.error(f"Error in scheduled analysis: {str(e)}")

        # Create task config
        task_config = TaskConfig(
            job_id=config.job_id,
            cron=config.cron,
            interval_seconds=config.interval_seconds,
            max_instances=config.max_instances,
            enabled=config.enabled,
        )

        # Register and schedule the task
        registry.register()(analysis_pipeline)
        job_id = await scheduler.schedule_function(analysis_pipeline.__name__, task_config)

        return ScheduleResponse(
            message=f"Scheduled analysis job {config.job_id}",
            job_id=config.job_id,
            config=config.dict(exclude={"job_id"}),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/maintenance", response_model=ScheduleResponse)
async def schedule_maintenance(config: MaintenanceSchedule, _: str = Depends(verify_api_key)):
    """Schedule recurring maintenance tasks."""
    try:
        # Generate job ID if not provided
        if not config.job_id:
            config.job_id = generate_job_id("maintenance")

        # Create the maintenance pipeline function
        async def maintenance_pipeline():
            try:
                if config.cleanup_old_logs:
                    logger.info("Running scheduled log cleanup")
                    raise NotImplementedError

                if config.vacuum_database:
                    logger.info("Running scheduled database vacuum")
                    raise NotImplementedError

                if config.update_indexes:
                    logger.info("Running scheduled index updates")
                    raise NotImplementedError

            except Exception as e:
                logger.error(f"Error in scheduled maintenance: {str(e)}")

        # Create task config
        task_config = TaskConfig(
            job_id=config.job_id,
            cron=config.cron,
            interval_seconds=config.interval_seconds,
            max_instances=config.max_instances,
            enabled=config.enabled,
        )

        # Register and schedule the task
        registry.register()(maintenance_pipeline)
        job_id = await scheduler.schedule_function(maintenance_pipeline.__name__, task_config)

        return ScheduleResponse(
            message=f"Scheduled maintenance job {config.job_id}",
            job_id=config.job_id,
            config=config.dict(exclude={"job_id"}),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(_: str = Depends(verify_api_key)):
    """List all scheduled jobs."""
    await scheduler.init()
    jobs = scheduler.get_jobs()
    logger.info(f"Jobs: {jobs}")
    job_info = []
    for job in jobs:
        job_info.append(
            {
                "id": job.id,
                "name": job.func.__name__ if hasattr(job, "func") else "Unknown",
                "next_run_time": job.next_run_time,
                # Add any other relevant job information
            }
        )
    return JobListResponse(jobs=job_info)


@router.put("/jobs/{job_id}/pause", response_model=SimpleJobResponse)
async def pause_job(job_id: str, _: str = Depends(verify_api_key)):
    """Pause a scheduled job."""
    try:
        await scheduler.init()
        scheduler.pause_job(job_id)
        return SimpleJobResponse(message=f"Paused job {job_id}", job_id=job_id)
    except JobLookupError:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


@router.put("/jobs/{job_id}/resume", response_model=SimpleJobResponse)
async def resume_job(job_id: str, _: str = Depends(verify_api_key)):
    """Resume a paused job."""
    try:
        await scheduler.init()
        scheduler.resume_job(job_id)
        return SimpleJobResponse(message=f"Resumed job {job_id}", job_id=job_id)
    except JobLookupError:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


@router.delete("/jobs/{job_id}", response_model=SimpleJobResponse)
async def delete_job(job_id: str, _: str = Depends(verify_api_key)):
    """Delete a scheduled job."""
    try:
        await scheduler.init()
        scheduler.remove_job(job_id)
        return SimpleJobResponse(message=f"Deleted job {job_id}", job_id=job_id)
    except JobLookupError:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


def _create_trigger(config: ScheduleBase):
    """Create an APScheduler trigger from schedule configuration."""
    if config.cron:
        try:
            return CronTrigger.from_crontab(config.cron)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid cron expression: {str(e)}")
    elif config.interval_seconds:
        return IntervalTrigger(
            seconds=config.interval_seconds,
            start_date=config.start_date,
            end_date=config.end_date,
        )
    else:
        raise HTTPException(status_code=400, detail="Either cron or interval_seconds must be specified")


class CreateTaskRequest(BaseModel):
    """Request model for creating a task from a function."""

    function_path: str
    config: TaskConfig


@router.post("/functions/schedule", response_model=SimpleJobResponse)
async def schedule_function(request: CreateTaskRequest, _: str = Depends(verify_api_key)):
    """Schedule a function to run on a recurring basis."""
    try:
        job_id = await scheduler.schedule_function(request.function_path, request.config)
        return SimpleJobResponse(message=f"Scheduled function {request.function_path}", job_id=job_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class RunFunctionRequest(BaseModel):
    """Request model for running a function once."""

    function_path: str
    parameters: Optional[Dict[str, Any]] = None


@router.post("/functions/run", response_model=SimpleJobResponse)
async def run_function(request: RunFunctionRequest, _: str = Depends(verify_api_key)):
    """Run a function once and return its job ID."""
    try:
        job_id = await registry.run_function_once(request.function_path, request.parameters)
        return SimpleJobResponse(message=f"Started function {request.function_path}", job_id=job_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs/{job_id}/status", response_model=JobStatus)
async def get_job_status(job_id: str, _: str = Depends(verify_api_key)):
    """Get the status of a job."""
    status = registry.get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return JobStatus


@router.get("/jobs/{job_id}/logs")
async def stream_job_logs(
    job_id: str,
    min_level: str = Query(
        default="INFO",
        description="Minimum log level to include (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    ),
    _: str = Depends(verify_api_key),
):
    """Stream logs for a specific job.

    Args:
        job_id: The ID of the job to get logs for
        min_level: Minimum log level to include (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    if not registry.get_job_status(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Validate log level
    try:
        log_filter = JobLogFilter(min_level=min_level.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid log level: {min_level}")

    async def event_generator():
        try:
            async for log in registry.get_job_logs(job_id, log_filter):
                yield {
                    "data": log.json(),
                    "event": "log",
                    "id": str(log.timestamp.timestamp()),
                }
        except Exception as e:
            logger.error(f"Error streaming logs for job {job_id}: {str(e)}")
            yield {"data": {"error": str(e)}, "event": "error"}

    return EventSourceResponse(event_generator())
