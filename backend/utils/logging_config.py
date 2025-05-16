"""Logging configuration for the application."""

import json
import logging
import logging.handlers
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from fastapi import Request, Response
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import LOGS_DIR, settings

# Initialize logger
logger = logging.getLogger(__name__)


def _cleanup_old_logs(
    log_dir: Path, base_name: str, max_files: int, logger: logging.Logger
):
    """Clean up old log files when max number is reached.

    Args:
        log_dir: Directory containing log files
        base_name: Base name of the log file (e.g., 'app.log')
        max_files: Maximum number of log files to keep (including base file)
        logger: Logger instance for logging cleanup operations
    """
    try:
        # Get all log files
        log_files = sorted(
            [f for f in log_dir.glob(f"{base_name}.*") if f.is_file()],
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )

        # If we exceed max files, delete oldest
        if len(log_files) > max_files:
            logger.info(f"Found {len(log_files)} log files, max is {max_files}")
            files_to_delete = log_files[max_files:]
            for old_file in files_to_delete:
                try:
                    logger.debug(f"Deleting old log file: {old_file}")
                    old_file.unlink()
                except OSError as e:
                    logger.error(f"Failed to delete old log file {old_file}: {e}")
            logger.info(f"Deleted {len(files_to_delete)} old log files")
    except Exception as e:
        logger.error(f"Error during log cleanup: {e}")


def setup_logging():
    """Set up logging configuration."""
    # Create logs directory if it doesn't exist
    os.makedirs(LOGS_DIR, exist_ok=True)

    # Set up root logger to capture all logs
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all logs, handlers will filter

    # Remove existing handlers to prevent duplicates if logging was configured elsewhere
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Create formatters and handlers
    formatter = logging.Formatter(settings.logging.format)
    file_formatter = logging.Formatter(settings.logging.file_format)

    # Console handler with configured console level
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.logging.log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler with configured file level (typically more verbose)
    log_file = LOGS_DIR / "app.log"
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,  # Create new file every day
        backupCount=settings.logging.backup_count,
        encoding="utf-8",
        delay=True,
    )
    file_handler.suffix = "%Y-%m-%d"  # Add date suffix to rotated files
    file_handler.setLevel(settings.logging.file_log_level)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Clean up old log files
    _cleanup_old_logs(
        LOGS_DIR,
        "app.log",
        settings.logging.backup_count + 1,  # +1 to account for the base log file
        root_logger,
    )

    # Set levels for noisy loggers
    for logger_name, level in settings.logging.noisy_loggers.items():
        logging.getLogger(logger_name).setLevel(level)


class EndpointLoggingRoute(APIRoute):
    """Custom API route that logs request and response information."""

    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            # Get endpoint logger
            endpoint_logger = logging.getLogger("endpoint")

            # Log request details
            body = await self._get_request_body(request)
            query_params = dict(request.query_params)
            path_params = request.path_params
            headers = dict(request.headers)
            # Remove sensitive headers
            headers.pop("authorization", None)
            headers.pop("cookie", None)

            endpoint_logger.debug(
                "Endpoint called",
                extra={
                    "endpoint": {
                        "method": request.method,
                        "url": str(request.url),
                        "path_params": path_params,
                        "query_params": query_params,
                        "body": body,
                        "headers": headers,
                    }
                },
            )

            response = await original_route_handler(request)
            return response

        return custom_route_handler

    @staticmethod
    async def _get_request_body(request: Request) -> Optional[Dict[str, Any]]:
        """Get the request body if it exists and is JSON."""
        try:
            body = await request.json()
            return body
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None


class EndpointLogFormatter(logging.Formatter):
    """Custom formatter for endpoint logs that handles structured data."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with custom handling for endpoint and response data."""
        # Make a copy of the record to avoid modifying the original
        record_copy = logging.makeLogRecord(record.__dict__)

        # Handle request logs
        if hasattr(record_copy, "request"):
            request_info = record_copy.request  # type: ignore
            record_copy.msg = (
                f"Request: {request_info['method']} {request_info['path']}\n"
                f"Query Params: {json.dumps(request_info['query_params'], indent=2)}\n"
                f"Path Params: {json.dumps(request_info['path_params'], indent=2)}\n"
                f"Headers: {json.dumps(request_info['headers'], indent=2)}\n"
                f"Body: {json.dumps(request_info['body'], indent=2)}"
            )

        # Handle response logs
        if hasattr(record_copy, "response"):
            response_info = record_copy.response  # type: ignore
            duration = response_info.get("duration_ms", 0)
            record_copy.msg = (
                f"Response: {response_info['status_code']} {response_info['path']}\n"
                f"Duration: {duration:.2f}ms\n"
                f"Headers: {json.dumps(response_info.get('headers', {}), indent=2)}\n"
                f"Body: {json.dumps(response_info.get('body', None), indent=2)}"
            )

        return super().format(record_copy)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging request timing and response status."""

    @staticmethod
    def _decode_bytes(data: bytes | memoryview) -> str:
        """Safely decode bytes to string."""
        try:
            if isinstance(data, memoryview):
                return data.tobytes().decode("utf-8")
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return str(data)

    async def dispatch(self, request: Request, call_next):
        # Record start time
        start_time = time.time()

        # Get endpoint logger
        endpoint_logger = logging.getLogger("endpoint")

        # Log request details
        request_body = None
        try:
            # Try to read the request body
            body = await request.body()
            if body:
                body_str = self._decode_bytes(body)
                try:
                    # Try to parse as JSON first
                    request_body = json.loads(body_str)
                except json.JSONDecodeError:
                    # If not JSON, use the string
                    request_body = body_str
        except Exception as e:
            endpoint_logger.warning(f"Failed to read request body: {str(e)}")

        # Log request with all details
        endpoint_logger.debug(
            "Request received",
            extra={
                "request": {
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": dict(request.query_params),
                    "path_params": request.path_params,
                    "headers": {
                        k: v
                        for k, v in request.headers.items()
                        if k.lower() not in ["authorization", "cookie"]
                    },
                    "body": request_body,
                }
            },
        )

        # Execute request and handle any errors
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            endpoint_logger.error(f"Request failed: {str(e)}")
            raise

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Try to get response body and headers
        response_body = None
        try:
            # Check if response is a streaming response
            if hasattr(response, "body_iterator"):
                response_body = "<StreamingResponse>"
            else:
                body = await response.body()  # type: ignore
                if body:
                    body_str = self._decode_bytes(body)
                    try:
                        response_body = json.loads(body_str)
                    except json.JSONDecodeError:
                        response_body = body_str
        except Exception as e:
            endpoint_logger.warning(f"Failed to read response body: {str(e)}")

        # Log response with all details
        endpoint_logger.debug(
            "Response sent",
            extra={
                "response": {
                    "status_code": status_code,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "headers": dict(response.headers),
                    "body": response_body,
                }
            },
        )

        return response


def setup_endpoint_logging():
    """Set up logging configuration for endpoint logging.

    This sets up endpoint-specific logging to write only to the log file,
    using the same file as the main application logging.
    """
    # Create a separate logger for endpoints
    endpoint_logger = logging.getLogger("endpoint")

    # Remove any existing handlers to avoid duplicates
    endpoint_logger.handlers.clear()

    # Prevent propagation to root logger since we want separate handling
    endpoint_logger.propagate = False

    # Set level to capture all endpoint logs at file level
    endpoint_logger.setLevel(settings.logging.file_log_level)

    # Add file handler that writes to the same log file as the main logger
    log_file = LOGS_DIR / "app.log"
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=settings.logging.backup_count,
        encoding="utf-8",
        delay=True,
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setLevel(settings.logging.file_log_level)
    file_formatter = EndpointLogFormatter(
        "%(asctime)s - endpoint - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    endpoint_logger.addHandler(file_handler)
