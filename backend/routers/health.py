"""Health check endpoints for system monitoring."""

import logging
import time
from typing import Any, Dict, List, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import check_connection
from ..utils.cache import cache

# Create router
router = APIRouter(prefix="/health", tags=["System"])

# Configure logger
logger = logging.getLogger(__name__)


class ServiceCheck(BaseModel):
    """Model for individual service health check."""

    name: str
    status: Literal["healthy", "unhealthy"]
    duration_ms: float | None = None
    error: str | None = None


class HealthCheckResponse(BaseModel):
    """Response model for health check endpoint."""

    status: Literal["healthy", "unhealthy"]
    timestamp: float
    duration_ms: float
    checks: List[ServiceCheck]


class SystemMetrics(BaseModel):
    """Model for system uptime metrics."""

    uptime: int = 0  # Uptime in seconds


class MetricsResponse(BaseModel):
    """Response model for metrics endpoint."""

    timestamp: float
    system: SystemMetrics


@router.get("/", summary="System health check", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Basic health check endpoint.

    Returns:
        A dictionary indicating service health status

    Raises:
        HTTPException: If any critical service is unhealthy
    """
    start_time = time.time()
    checks: List[ServiceCheck] = []

    # Check database connection
    try:
        db_start = time.time()
        db_healthy = await check_connection()
        db_duration = time.time() - db_start

        checks.append(
            ServiceCheck(
                name="database",
                status="healthy" if db_healthy else "unhealthy",
                duration_ms=round(db_duration * 1000, 2),
            )
        )

        if not db_healthy:
            logger.error("Database health check failed")
    except Exception as e:
        logger.error(f"Database health check error: {e}")
        checks.append(
            ServiceCheck(
                name="database",
                status="unhealthy",
                error=str(e),
            )
        )

    # Check Redis cache
    try:
        cache_start = time.time()
        cache_key = "health_check"
        await cache.set(cache_key, "ok", ttl=60)
        cache_value = await cache.get(cache_key)
        cache_duration = time.time() - cache_start

        cache_healthy = cache_value == "ok"
        checks.append(
            ServiceCheck(
                name="cache",
                status="healthy" if cache_healthy else "unhealthy",
                duration_ms=round(cache_duration * 1000, 2),
            )
        )

        if not cache_healthy:
            logger.error("Cache health check failed")
    except Exception as e:
        logger.error(f"Cache health check error: {e}")
        checks.append(
            ServiceCheck(
                name="cache",
                status="unhealthy",
                error=str(e),
            )
        )

    # Determine overall health
    all_healthy = all(check.status == "healthy" for check in checks)
    status = "healthy" if all_healthy else "unhealthy"

    # Create response
    response = HealthCheckResponse(
        status=status,
        timestamp=time.time(),
        duration_ms=round((time.time() - start_time) * 1000, 2),
        checks=checks,
    )

    # Return 503 if unhealthy
    if not all_healthy:
        raise HTTPException(status_code=503, detail=response.dict())

    return response


@router.get("/metrics", summary="System metrics", response_model=MetricsResponse)
async def system_metrics() -> MetricsResponse:
    """Endpoint for system metrics.

    Returns:
        A dictionary of system metrics
    """
    # Start with basic metrics
    metrics = MetricsResponse(
        timestamp=time.time(),
        system=SystemMetrics(
            uptime=0,  # TODO: Implement actual uptime tracking
        ),
    )

    # Add database metrics if available
    try:
        # TODO: Implement database metrics
        pass
    except Exception as e:
        logger.error(f"Error collecting database metrics: {e}")

    # Add cache metrics if available
    try:
        # TODO: Implement Redis metrics
        pass
    except Exception as e:
        logger.error(f"Error collecting cache metrics: {e}")

    return metrics
