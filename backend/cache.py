"""Cache configuration and utilities."""

import logging
from typing import Optional

from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis

from .config import settings

logger = logging.getLogger(__name__)


async def init_cache() -> None:
    """Initialize the FastAPI cache with Redis backend.

    This should be called during application startup.
    """
    try:
        redis = aioredis.from_url(settings.redis.uri, encoding="utf8", decode_responses=True)
        FastAPICache.init(RedisBackend(redis), prefix="vroom-cache")
        logger.info("Cache initialized with Redis backend")
    except Exception as e:
        logger.error(f"Failed to initialize cache: {str(e)}")
        raise


async def invalidate_cache_keys(*keys: str) -> None:
    """Invalidate specific cache keys.

    Args:
        *keys: Variable number of cache keys to invalidate
    """
    try:
        for key in keys:
            await FastAPICache.clear(namespace=key)
            logger.debug(f"Invalidated cache key: {key}")
    except Exception as e:
        logger.error(f"Failed to invalidate cache keys: {str(e)}")
        raise
