"""Scheduling endpoints for recurring tasks."""

import logging
import uuid
from datetime import datetime
from typing import Optional

from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from pymongo import MongoClient

from ..config import settings
from ..logic import analysis, scraping
from ..schemas.analyzed_listings import AnalyzedListingDocument
from ..schemas.listings import ListingDocument
from ..security import verify_api_key

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize MongoDB client
client = MongoClient(settings.database.uri)

# Initialize scheduler with MongoDB job store and configuration
scheduler = AsyncIOScheduler(
    jobstores={"default": MongoDBJobStore(client=client, database=settings.database.database_name)},
    timezone=settings.scheduler.timezone,
    job_defaults=settings.scheduler.job_defaults,
    executors=settings.scheduler.executors,
)

router = APIRouter(prefix="/schedule", tags=["scheduling"])


class ScheduleBase(BaseModel):
    """Base model for schedule configuration."""

    job_id: Optional[str] = Field(default=None, description="Optional job ID. If not provided, one will be generated.")
    cron: Optional[str] = None  # Cron expression (e.g. "0 0 * * *" for daily at midnight)
    interval_seconds: Optional[int] = None  # Interval in seconds
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class ScrapeSchedule(ScheduleBase):
    """Schedule configuration for scraping tasks."""

    url: HttpUrl
    analyze: bool = False  # Whether to analyze scraped listings


class AnalysisSchedule(ScheduleBase):
    """Schedule configuration for analysis tasks."""

    retry_failed: bool = False  # Whether to retry failed analyses


class QuerySchedule(ScheduleBase):
    """Schedule configuration for query tasks."""

    query: dict  # MongoDB query to execute
    target: str  # Either "listings" or "analyzed"


def generate_job_id(prefix: str) -> str:
    """Generate a unique job ID with a meaningful prefix."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@router.post("/scrape")
async def schedule_scraping(config: ScrapeSchedule, _: str = Depends(verify_api_key)):
    """Schedule a recurring scraping task."""
    try:
        # Generate job ID if not provided
        if not config.job_id:
            config.job_id = generate_job_id("scrape")

        # Choose the appropriate scraping function
        func = scraping.scrape_analyze_and_save if config.analyze else scraping.scrape_and_save

        # Create trigger based on configuration
        trigger = _create_trigger(config)

        # Add job to scheduler
        scheduler.add_job(func, trigger=trigger, args=[str(config.url)], id=config.job_id, replace_existing=True)

        return {"message": f"Scheduled scraping job {config.job_id}", "job_id": config.job_id, "config": config}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/analysis")
async def schedule_analysis(config: AnalysisSchedule, _: str = Depends(verify_api_key)):
    """Schedule a recurring analysis task."""
    try:
        # Generate job ID if not provided
        if not config.job_id:
            config.job_id = generate_job_id("analysis")

        # Choose the appropriate analysis function
        func = analysis.retry_failed_analyses if config.retry_failed else analysis.analyze_new_listings

        # Create trigger based on configuration
        trigger = _create_trigger(config)

        # Add job to scheduler
        scheduler.add_job(func, trigger=trigger, id=config.job_id, replace_existing=True)

        return {"message": f"Scheduled analysis job {config.job_id}", "job_id": config.job_id, "config": config}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/query")
async def schedule_query(config: QuerySchedule, _: str = Depends(verify_api_key)):
    """Schedule a recurring query task."""
    try:
        # Generate job ID if not provided
        if not config.job_id:
            config.job_id = generate_job_id("query")

        # Create trigger based on configuration
        trigger = _create_trigger(config)

        # Choose the appropriate document class
        doc_class = AnalyzedListingDocument if config.target == "analyzed" else ListingDocument

        # Create the query function
        async def execute_query():
            try:
                results = await doc_class.find(config.query).to_list()
                logger.info(f"Scheduled query {config.job_id} found {len(results)} results")
                return results
            except Exception as e:
                logger.error(f"Error executing scheduled query {config.job_id}: {str(e)}")
                return []

        # Add job to scheduler
        scheduler.add_job(execute_query, trigger=trigger, id=config.job_id, replace_existing=True)

        return {"message": f"Scheduled query job {config.job_id}", "job_id": config.job_id, "config": config}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs")
async def list_jobs(_: str = Depends(verify_api_key)):
    """List all scheduled jobs."""
    jobs = scheduler.get_jobs()
    logger.info(f"Jobs: {jobs}")
    return [
        {"id": job.id, "next_run_time": job.next_run_time, "func": job.func.__name__, "trigger": str(job.trigger)}
        for job in jobs
    ]


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, _: str = Depends(verify_api_key)):
    """Delete a scheduled job."""
    try:
        scheduler.remove_job(job_id)
        return {"message": f"Deleted job {job_id}"}
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
        return IntervalTrigger(seconds=config.interval_seconds, start_date=config.start_date, end_date=config.end_date)
    else:
        raise HTTPException(status_code=400, detail="Either cron or interval_seconds must be specified")
