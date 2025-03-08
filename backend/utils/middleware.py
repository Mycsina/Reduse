"""Middleware for request handling and error processing."""

import logging
import time
from typing import Callable, Dict

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .errors import VroomError, convert_exception

# Configure logger
logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for global error handling."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and handle any errors.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            The response
        """
        try:
            # Process the request
            return await call_next(request)
        except Exception as exc:
            # Convert to application error
            error = convert_exception(exc)

            # Log the error
            error.log()

            # Return JSON response with error details
            return JSONResponse(
                status_code=error.status_code,
                content=error.to_dict(),
            )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging request details."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request details and timing.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            The response
        """
        # Record start time
        start_time = time.time()

        # Extract request details
        path = request.url.path
        method = request.method
        client = request.client.host if request.client else "unknown"

        # Process request
        response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time

        # Prepare log details
        log_dict = {
            "path": path,
            "method": method,
            "client": client,
            "status_code": response.status_code,
            "process_time_ms": round(process_time * 1000, 2),
        }

        # Log with appropriate level based on status code
        if response.status_code >= 500:
            logger.error(f"Request failed: {method} {path}", extra=log_dict)
        elif response.status_code >= 400:
            logger.warning(f"Request error: {method} {path}", extra=log_dict)
        else:
            logger.info(f"Request processed: {method} {path}", extra=log_dict)

        return response


def setup_middleware(app: FastAPI) -> None:
    """Set up all middleware for the application.

    Args:
        app: The FastAPI application
    """
    # Add error handling middleware
    app.add_middleware(ErrorHandlingMiddleware)

    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware)
