"""Scheduling endpoints for recurring tasks."""

import logging
import uuid
from datetime import datetime
from typing import Optional, List

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


def generate_job_id(prefix: str) -> str:
    """Generate a unique job ID with a meaningful prefix."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@router.post("/scrape")
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

        # Create trigger based on configuration
        trigger = _create_trigger(config)

        # Add job to scheduler with configuration
        scheduler.add_job(
            scraping_pipeline,
            trigger=trigger,
            id=config.job_id,
            replace_existing=True,
            max_instances=config.max_instances,
        )

        return {
            "message": f"Scheduled scraping job {config.job_id}",
            "job_id": config.job_id,
            "config": config.dict(exclude={"job_id"}),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/scrape/olx")
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

        # Create trigger based on configuration
        trigger = _create_trigger(config)

        # Add job to scheduler with configuration
        scheduler.add_job(
            olx_scraping_pipeline,
            trigger=trigger,
            id=config.job_id,
            replace_existing=True,
            max_instances=config.max_instances,
        )

        return {
            "message": f"Scheduled OLX scraping job {config.job_id}",
            "job_id": config.job_id,
            "config": config.dict(exclude={"job_id"}),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/analysis")
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

        # Create trigger based on configuration
        trigger = _create_trigger(config)

        # Add job to scheduler with configuration
        scheduler.add_job(
            analysis_pipeline,
            trigger=trigger,
            id=config.job_id,
            replace_existing=True,
            max_instances=config.max_instances,
        )

        return {
            "message": f"Scheduled analysis job {config.job_id}",
            "job_id": config.job_id,
            "config": config.dict(exclude={"job_id"}),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/maintenance")
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
                    # TODO: Implement log cleanup

                if config.vacuum_database:
                    logger.info("Running scheduled database vacuum")
                    # TODO: Implement database vacuum

                if config.update_indexes:
                    logger.info("Running scheduled index updates")
                    # TODO: Implement index updates

            except Exception as e:
                logger.error(f"Error in scheduled maintenance: {str(e)}")

        # Create trigger based on configuration
        trigger = _create_trigger(config)

        # Add job to scheduler with configuration
        scheduler.add_job(
            maintenance_pipeline,
            trigger=trigger,
            id=config.job_id,
            replace_existing=True,
            max_instances=config.max_instances,
        )

        return {
            "message": f"Scheduled maintenance job {config.job_id}",
            "job_id": config.job_id,
            "config": config.dict(exclude={"job_id"}),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs")
async def list_jobs(_: str = Depends(verify_api_key)):
    """List all scheduled jobs."""
    jobs = scheduler.get_jobs()
    logger.info(f"Jobs: {jobs}")
    return [
        {
            "id": job.id,
            "next_run_time": job.next_run_time,
            "func": job.func.__name__,
            "trigger": str(job.trigger),
            "max_instances": job.max_instances,
        }
        for job in jobs
    ]


@router.put("/jobs/{job_id}/pause")
async def pause_job(job_id: str, _: str = Depends(verify_api_key)):
    """Pause a scheduled job."""
    try:
        scheduler.pause_job(job_id)
        return {"message": f"Paused job {job_id}"}
    except JobLookupError:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


@router.put("/jobs/{job_id}/resume")
async def resume_job(job_id: str, _: str = Depends(verify_api_key)):
    """Resume a paused job."""
    try:
        scheduler.resume_job(job_id)
        return {"message": f"Resumed job {job_id}"}
    except JobLookupError:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


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
