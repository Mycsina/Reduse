"""Standardized error handling for the application."""

import logging
from typing import Any, Dict, Optional, Type

# Configure logger
logger = logging.getLogger(__name__)


class ReduseError(Exception):
    """Base exception class for all application errors."""

    def __init__(
        self,
        message: str = "An error occurred",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
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
        log_context = {
            "error_type": self.__class__.__name__,
            "status_code": self.status_code,
            **self.details,
        }
        logger.log(level, f"{self.message}", extra=log_context)


# AI Provider Errors
class ProviderError(ReduseError):
    """Base class for AI provider errors."""

    pass


class RateLimitError(ProviderError):
    """Provider rate limit exceeded."""

    retry_after: float = 0

    def __init__(self, provider: str, retry_after: Optional[float] = None):
        """Initialize rate limit error.

        Args:
            provider: Name of the AI provider
            retry_after: Seconds to wait before retrying
        """
        message = f"Rate limit exceeded for provider {provider}"
        details = {"provider": provider, "retry_after": retry_after or 0}
        self.retry_after = retry_after or 0

        super().__init__(message=message, status_code=429, details=details)
