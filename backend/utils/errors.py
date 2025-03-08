"""Standardized error handling for the application."""

import logging
from typing import Any, Dict, Optional, Type

# Configure logger
logger = logging.getLogger(__name__)


class VroomError(Exception):
    """Base exception class for all application errors."""

    def __init__(
        self, message: str = "An error occurred", status_code: int = 500, details: Optional[Dict[str, Any]] = None
    ):
        """Initialize the error.

        Args:
            message: Human-readable error message
            status_code: HTTP status code
            details: Additional error details
        """
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the error to a dictionary for API responses.

        Returns:
            Dict containing error details
        """
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "status_code": self.status_code,
            "details": self.details,
        }

    def log(self, level: int = logging.ERROR) -> None:
        """Log the error with appropriate level and context.

        Args:
            level: Logging level to use
        """
        log_context = {"error_type": self.__class__.__name__, "status_code": self.status_code, **self.details}
        logger.log(level, f"{self.message}", extra=log_context)


# Database Errors
class DatabaseError(VroomError):
    """Base class for database-related errors."""

    pass


class ConnectionError(DatabaseError):
    """Error establishing database connection."""

    pass


class QueryError(DatabaseError):
    """Error executing database query."""

    pass


class DocumentNotFoundError(DatabaseError):
    """Requested document not found."""

    def __init__(self, document_type: str, query: Optional[Dict[str, Any]] = None):
        """Initialize document not found error.

        Args:
            document_type: Type of document that wasn't found
            query: Query used to search for the document
        """
        message = f"{document_type} not found"
        super().__init__(message=message, status_code=404, details={"document_type": document_type, "query": query})


# AI Provider Errors
class AIProviderError(VroomError):
    """Base class for AI provider errors."""

    pass


class RateLimitError(AIProviderError):
    """Provider rate limit exceeded."""

    def __init__(self, provider: str, retry_after: Optional[float] = None):
        """Initialize rate limit error.

        Args:
            provider: Name of the AI provider
            retry_after: Seconds to wait before retrying
        """
        message = f"Rate limit exceeded for provider {provider}"
        details = {"provider": provider}

        if retry_after is not None:
            details["retry_after"] = retry_after

        super().__init__(message=message, status_code=429, details=details)


class ProviderResponseError(AIProviderError):
    """Error in AI provider response."""

    pass


# Scraper Errors
class ScraperError(VroomError):
    """Base class for scraper errors."""

    pass


class BlockedError(ScraperError):
    """Scraper access blocked."""

    pass


class ParseError(ScraperError):
    """Error parsing scraped content."""

    pass


# Validation Errors
class ValidationError(VroomError):
    """Base class for validation errors."""

    def __init__(self, field: str, message: str):
        """Initialize validation error.

        Args:
            field: Name of the field that failed validation
            message: Validation error message
        """
        super().__init__(message=message, status_code=422, details={"field": field})


# Function to convert standard exceptions to application exceptions
def convert_exception(exception: Exception, default_error_class: Type[VroomError] = VroomError) -> VroomError:
    """Convert a standard exception to an application exception.

    Args:
        exception: The original exception
        default_error_class: Default error class to use

    Returns:
        VroomError: Application-specific error
    """
    if isinstance(exception, VroomError):
        return exception

    message = str(exception)
    error_class = default_error_class

    # Attempt to map common exceptions to appropriate error types
    if isinstance(exception, (ConnectionRefusedError, TimeoutError)):
        error_class = ConnectionError
    elif isinstance(exception, KeyError):
        error_class = ValidationError
        return ValidationError(field=str(exception), message=f"Missing required field: {exception}")
    elif isinstance(exception, ValueError):
        error_class = ValidationError
        return ValidationError(field="value", message=message)

    return error_class(message=message)
