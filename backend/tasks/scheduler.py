"""Task scheduler for periodic jobs."""

# TODO typing

import logging
from datetime import datetime
from typing import Optional, Union

from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pymongo import MongoClient

from ..config import settings
from .function_introspection import \
    introspect  # Keep import for type hinting if needed, but don't call at top level
from .task_registry import TaskConfig

logger = logging.getLogger(__name__)


class Scheduler:
    """Task scheduler with dynamic task registration and MongoDB persistence."""

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.client: Optional[MongoClient] = None

    async def init(self):
        """Initialize the scheduler with MongoDB connection."""
        if self.scheduler is not None:
            return

        self.client = MongoClient(settings.database.uri)
        self.scheduler = AsyncIOScheduler(
            jobstores={
                "default": MongoDBJobStore(
                    client=self.client, database=settings.database.database_name
                )
            },
            timezone=settings.scheduler.timezone,
            job_defaults=settings.scheduler.job_defaults,
            executors=settings.scheduler.executors,
        )

    def create_trigger(self, config: TaskConfig) -> Union[CronTrigger, IntervalTrigger]:
        """Create an APScheduler trigger from task configuration."""
        if config.cron:
            return CronTrigger.from_crontab(config.cron)
        elif config.interval_seconds:
            return IntervalTrigger(seconds=config.interval_seconds)
        raise ValueError("Either cron or interval_seconds must be specified")

    async def schedule_function(self, function_path: str, config: TaskConfig) -> str:
        """Schedule a discovered function as a task."""
        await self.init()

        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")

        # Get discovery instance inside the method
        discovery = introspect()
        task_func = discovery.create_task_from_function(function_path)
        if task_func is None:
            raise ValueError(
                f"Function {function_path} not found or could not be converted to task"
            )

        job_id = (
            config.job_id
            or f"{function_path.replace('.', '_')}_{datetime.utcnow().timestamp()}"
        )
        trigger = self.create_trigger(config)

        # Schedule the task with its parameters
        self.scheduler.add_job(
            task_func,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            max_instances=config.max_instances,
            kwargs=config.parameters,
        )

        if not config.enabled:
            self.scheduler.pause_job(job_id)

        return job_id

    def start(self):
        """Start the scheduler."""
        if self.scheduler and not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()

    def get_jobs(self):
        """Get all scheduled jobs."""
        return self.scheduler.get_jobs() if self.scheduler else []

    def add_job(self, *args, **kwargs):
        """Add a job to the scheduler."""
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")
        return self.scheduler.add_job(*args, **kwargs)

    def pause_job(self, job_id: str):
        """Pause a job."""
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")
        return self.scheduler.pause_job(job_id)

    def resume_job(self, job_id: str):
        """Resume a job."""
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")
        return self.scheduler.resume_job(job_id)

    def remove_job(self, job_id: str):
        """Remove a job."""
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")
        return self.scheduler.remove_job(job_id)


# Global scheduler instance
scheduler = Scheduler()


def start_scheduler():
    """Start the task scheduler."""
    scheduler.start()
