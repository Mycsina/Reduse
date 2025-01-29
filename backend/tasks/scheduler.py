"""Task scheduler for periodic jobs with dynamic task registration and introspection capabilities."""

import asyncio
import importlib
import inspect
import logging
import os
import pkgutil
import uuid
from datetime import datetime
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    Union,
    get_type_hints,
)

from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pydantic import BaseModel, Field
from pymongo import MongoClient

from ..config import settings

logger = logging.getLogger(__name__)


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


class FunctionInfo(BaseModel):
    """Information about a discovered function."""

    module_name: str
    function_name: str
    full_path: str
    doc: Optional[str]
    is_async: bool
    parameters: Dict[str, Dict[str, Any]]
    return_type: Optional[str]


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
    """Registry for scheduled tasks with introspection capabilities."""

    def __init__(self):
        self.tasks: Dict[str, Callable] = {}
        self.configs: Dict[str, Type[TaskConfig]] = {}
        self.discovered_functions: Dict[str, FunctionInfo] = {}
        self.job_logs: Dict[str, asyncio.Queue[JobLogMessage]] = {}
        self.job_statuses: Dict[str, JobStatus] = {}
        self.job_log_filters: Dict[str, List[JobLogFilter]] = (
            {}
        )  # Multiple filters per job for different subscribers

    def register(self, config_class: Optional[Type[TaskConfig]] = None):
        """Decorator to register a task with optional custom configuration."""

        def decorator(func: Callable):
            task_name = func.__name__
            self.tasks[task_name] = func
            if config_class is not None:
                self.configs[task_name] = config_class
            return func

        return decorator

    def get_type_str(self, type_hint: Any) -> str:
        """Convert a type hint to a string representation, handling special cases."""
        try:
            if type_hint is None:
                return "None"
            if hasattr(type_hint, "__name__"):
                return type_hint.__name__
            if hasattr(type_hint, "_name"):  # Handle Union types
                return type_hint._name or str(type_hint)

            # Handle special cases
            origin = getattr(type_hint, "__origin__", None)
            if origin is Union:
                args = getattr(type_hint, "__args__", [])
                types = [self.get_type_str(arg) for arg in args]
                return f"Union[{', '.join(types)}]"

            # For other generic types (List, Dict, etc.)
            if origin is not None:
                args = getattr(type_hint, "__args__", [])
                origin_name = getattr(origin, "__name__", str(origin))
                if args:
                    args_str = ", ".join(self.get_type_str(arg) for arg in args)
                    return f"{origin_name}[{args_str}]"
                return origin_name

            # Fallback
            return str(type_hint)
        except Exception as e:
            logger.debug(f"Error converting type hint to string: {str(e)}")
            return "Any"

    def discover_functions(
        self, package_path: str = "backend"
    ) -> Dict[str, FunctionInfo]:
        """Discover all functions in the given package path.

        Args:
            package_path: The package to search in. Defaults to "backend" to search the entire backend package.
                Can be either:
                - A dot-separated Python package path (e.g. "backend.services")
                - A relative path starting with "." (e.g. "." for current package)
        """
        logger.info(f"Discovering functions in {package_path}")
        self.discovered_functions.clear()

        def explore_module(module):
            for name, obj in inspect.getmembers(module):
                if inspect.isfunction(obj) and not name.startswith("_"):
                    try:
                        # Get the absolute file path of the function's source code
                        try:
                            source_file = inspect.getfile(obj)
                            # Check if the function is from our project directory
                            if not source_file.startswith(
                                os.path.dirname(os.path.dirname(__file__))
                            ):
                                continue
                        except (TypeError, ValueError):
                            # If we can't get the source file, skip this function
                            continue

                        # Get function signature and type hints
                        sig = inspect.signature(obj)
                        try:
                            type_hints = get_type_hints(obj)
                        except Exception:
                            # If we can't get type hints, use empty dict
                            type_hints = {}

                        # Extract parameter information
                        params = {}
                        for param_name, param in sig.parameters.items():
                            if param_name == "self":  # Skip self parameter
                                continue
                            param_info = {
                                "required": param.default == param.empty,
                                "default": (
                                    None
                                    if param.default == param.empty
                                    else param.default
                                ),
                                "type": self.get_type_str(
                                    type_hints.get(param_name, Any)
                                ),
                                "description": None,  # Could be extracted from docstring in the future
                            }
                            params[param_name] = param_info

                        # Create function info
                        func_info = FunctionInfo(
                            module_name=module.__name__,
                            function_name=name,
                            full_path=f"{module.__name__}.{name}",
                            doc=inspect.getdoc(obj),
                            is_async=inspect.iscoroutinefunction(obj),
                            parameters=params,
                            return_type=self.get_type_str(
                                type_hints.get("return", Any)
                            ),
                        )
                        logger.debug(f"Discovered function: {func_info.full_path}")
                        self.discovered_functions[func_info.full_path] = func_info
                    except Exception as e:
                        logger.debug(f"Error processing function {name}: {str(e)}")

        def explore_package(package_name: str):
            try:
                # Handle relative imports
                if package_name.startswith("."):
                    # Get the parent package name from the caller's frame
                    current_frame = inspect.currentframe()
                    if current_frame is not None:
                        caller_frame = current_frame.f_back
                        if caller_frame is not None:
                            caller_frame = caller_frame.f_back
                            if caller_frame is not None:
                                caller_module = inspect.getmodule(caller_frame)
                                if caller_module and caller_module.__package__:
                                    # Convert relative import to absolute
                                    if package_name == ".":
                                        package_name = "backend"  # Always start from the root backend package
                                    else:
                                        package_name = f"backend{package_name}"

                logger.debug(f"Importing package: {package_name}")
                package = importlib.import_module(package_name)
                explore_module(package)

                # Explore all submodules
                if hasattr(package, "__path__"):
                    for _, name, is_pkg in pkgutil.iter_modules(package.__path__):
                        full_name = f"{package_name}.{name}"
                        explore_package(full_name)
            except Exception as e:
                logger.warning(f"Error exploring package {package_name}: {str(e)}")
            finally:
                # Clean up frame references to avoid memory leaks
                if "current_frame" in locals():
                    del current_frame

        explore_package(package_path)
        return self.discovered_functions

    def get_function_info(self, full_path: str) -> Optional[FunctionInfo]:
        """Get information about a discovered function."""
        if not self.discovered_functions:
            self.discover_functions()
        return self.discovered_functions.get(full_path)

    def create_task_from_function(self, full_path: str) -> Optional[Callable]:
        """Create a task from a discovered function."""
        func_info = self.get_function_info(full_path)
        if not func_info:
            return None

        try:
            module = importlib.import_module(func_info.module_name)
            func = getattr(module, func_info.function_name)

            # Create a wrapper that handles parameter passing
            async def task_wrapper(**parameters):
                try:
                    if func_info.is_async:
                        return await func(**parameters)
                    return func(**parameters)
                except Exception as e:
                    logger.error(f"Error executing task {full_path}: {str(e)}")
                    raise

            # Store the original function info
            task_wrapper.func_info = func_info
            return task_wrapper
        except Exception as e:
            logger.error(f"Error creating task from function {full_path}: {str(e)}")
            return None

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

        # Get the function
        task_func = self.create_task_from_function(function_path)
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

        # Create task from function
        task_func = registry.create_task_from_function(function_path)
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
