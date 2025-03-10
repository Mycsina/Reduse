"""Task scheduler for periodic jobs with dynamic task registration and introspection capabilities."""

import asyncio
import inspect
import logging
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from .function_introspection import introspect

logger = logging.getLogger(__name__)


functionDiscovery = introspect()


class TaskConfig(BaseModel):
    """Base configuration for scheduled tasks."""

    job_id: Optional[str] = Field(
        default=None,
        description="Optional job ID. If not provided, one will be generated.",
    )
    cron: Optional[str] = (
        None  # Cron expression (e.g. "0 0 * * *" for daily at midnight)
    )
    interval_seconds: Optional[int] = None  # Interval in seconds
    max_instances: int = Field(
        default=1, ge=1, le=10
    )  # Maximum number of concurrent instances
    enabled: bool = True  # Whether the job should start enabled
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Parameters to pass to the task function"
    )


class JobLogMessage(BaseModel):
    """A log message from a running job."""

    timestamp: datetime
    level: str
    level_number: int  # Numeric level for filtering
    message: str


class JobLogFilter(BaseModel):
    """Filter configuration for job logs."""

    min_level: str = Field(
        default="INFO",
        description="Minimum log level to include (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    @property
    def level_number(self) -> int:
        """Get the numeric value for the minimum log level."""
        return getattr(logging, self.min_level.upper(), logging.INFO)


class JobStatus(BaseModel):
    """Status of a running job."""

    job_id: str
    status: str  # "running", "completed", "failed"
    result: Optional[Any] = None
    error: Optional[str] = None


class TaskRegistry:
    """Registry for scheduled tasks."""

    def __init__(self):
        self.tasks: Dict[str, Callable] = {}
        self.configs: Dict[str, Type[TaskConfig]] = {}
        self.job_logs: Dict[str, asyncio.Queue[JobLogMessage]] = {}
        self.job_statuses: Dict[str, JobStatus] = {}
        self.job_log_filters: Dict[str, List[JobLogFilter]] = {}
        self.function_discovery = functionDiscovery

    def register(self, config_class: Optional[Type[TaskConfig]] = None):
        """Decorator to register a task with optional custom configuration."""

        def decorator(func: Callable):
            task_name = func.__name__
            self.tasks[task_name] = func
            if config_class is not None:
                self.configs[task_name] = config_class
            return func

        return decorator

    def get_task(self, name: str) -> Optional[Callable]:
        """Get a registered task by name."""
        return self.tasks.get(name)

    def get_config_class(self, name: str) -> Type[TaskConfig]:
        """Get the configuration class for a task."""
        return self.configs.get(name, TaskConfig)

    def list_tasks(self) -> Dict[str, Dict[str, Any]]:
        """List all registered tasks with their metadata."""
        tasks_info = {}
        for name, func in self.tasks.items():
            config_class = self.configs.get(name, TaskConfig)
            tasks_info[name] = {
                "name": name,
                "doc": inspect.getdoc(func) or "",
                "signature": str(inspect.signature(func)),
                "config_class": config_class.__name__,
                "config_schema": config_class.schema(),
            }
        return tasks_info

    def create_job_logger(self, job_id: str) -> logging.Logger:
        """Create a logger that will send logs to the job's queue."""
        # Create a queue for this job's logs
        self.job_logs[job_id] = asyncio.Queue()
        self.job_log_filters[job_id] = []  # Initialize empty list of filters

        # Create a custom logger
        job_logger = logging.getLogger(f"job.{job_id}")
        job_logger.setLevel(logging.DEBUG)  # Capture all levels, filter on delivery

        class QueueHandler(logging.Handler):
            def emit(handler_self, record):  # type: ignore
                try:
                    log_message = JobLogMessage(
                        timestamp=datetime.fromtimestamp(record.created),
                        level=record.levelname,
                        level_number=record.levelno,
                        message=record.getMessage(),
                    )
                    # Only queue the message if it passes at least one filter
                    filters = self.job_log_filters.get(job_id, [])
                    if not filters or any(
                        log_message.level_number >= f.level_number for f in filters
                    ):
                        asyncio.create_task(self.job_logs[job_id].put(log_message))
                except Exception as e:
                    logger.error(f"Error in job logger: {str(e)}")

        job_logger.addHandler(QueueHandler())
        return job_logger

    async def get_job_logs(
        self, job_id: str, log_filter: Optional[JobLogFilter] = None
    ) -> AsyncGenerator[JobLogMessage, None]:
        """Get logs for a specific job with optional filtering.

        Args:
            job_id: The ID of the job to get logs for
            log_filter: Optional filter configuration for log levels
        """
        if job_id not in self.job_logs:
            return

        # Add filter for this subscriber
        if log_filter:
            self.job_log_filters[job_id].append(log_filter)

        queue = self.job_logs[job_id]
        try:
            while True:
                try:
                    message = await queue.get()
                    # Apply filter if provided
                    if (
                        not log_filter
                        or message.level_number >= log_filter.level_number
                    ):
                        yield message
                    queue.task_done()
                except asyncio.CancelledError:
                    break
        finally:
            # Clean up when subscriber disconnects
            if log_filter and job_id in self.job_log_filters:
                self.job_log_filters[job_id].remove(log_filter)
                if not self.job_log_filters[job_id]:  # If no more subscribers
                    del self.job_log_filters[job_id]
                    if job_id in self.job_logs:
                        del self.job_logs[job_id]

    async def run_function_once(
        self, function_path: str, parameters: Optional[Dict[str, Any]] = None
    ) -> str:
        """Run a function once and return its job ID."""
        # Create a unique job ID
        job_id = str(uuid.uuid4())

        # Get the function using FunctionDiscovery
        task_func = self.function_discovery.create_task_from_function(function_path)
        if task_func is None:
            raise ValueError(
                f"Function {function_path} not found or could not be converted to task"
            )

        # Create a logger for this job
        job_logger = self.create_job_logger(job_id)

        # Create initial job status
        self.job_statuses[job_id] = JobStatus(job_id=job_id, status="running")

        # Create and run the task
        async def run_task():
            try:
                job_logger.info(f"Starting job {job_id} for function {function_path}")
                result = await task_func(**(parameters or {}))

                # Log the function output
                if result is not None:
                    if isinstance(result, (str, int, float, bool)):
                        job_logger.info(f"Function output: {result}")
                    else:
                        # For complex objects, try to format them nicely
                        try:
                            if hasattr(result, "dict"):  # For Pydantic models
                                job_logger.info(f"Function output: {result.dict()}")
                            else:
                                job_logger.info(f"Function output: {result}")
                        except Exception:
                            job_logger.info(f"Function output: {result}")

                job_logger.info(f"Job {job_id} completed successfully")

                # Update job status
                self.job_statuses[job_id] = JobStatus(
                    job_id=job_id, status="completed", result=result
                )
            except Exception as e:
                error_msg = str(e)
                job_logger.error(f"Job {job_id} failed: {error_msg}")

                # Update job status
                self.job_statuses[job_id] = JobStatus(
                    job_id=job_id, status="failed", error=error_msg
                )

        # Start the task
        asyncio.create_task(run_task())
        return job_id

    def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """Get the status of a job."""
        return self.job_statuses.get(job_id)


# Global task registry
registry = TaskRegistry()
