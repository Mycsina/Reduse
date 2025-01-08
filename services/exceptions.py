"""Custom exceptions for the scraper module."""


class ScraperException(Exception):
    """Base exception for all scraper-related errors."""

    pass


class BrowserException(ScraperException):
    """Errors related to browser operations."""

    pass


class BrowserPoolExhausted(BrowserException):
    """Raised when no browsers are available in the pool."""

    pass


class RateLimitExceeded(ScraperException):
    """Raised when rate limiting is detected."""

    pass


class ParseError(ScraperException):
    """Errors during HTML parsing."""

    pass


class ContentNotFound(ParseError):
    """Required content was not found in the page."""

    pass


class NetworkError(ScraperException):
    """Network-related errors."""

    pass


class TimeoutError(NetworkError):
    """Operation timed out."""

    pass
