"""Redis-based caching implementation."""

import asyncio
import json
import logging
import pickle
from typing import Any, Optional, Type, TypeVar, Union, cast

import redis.asyncio as aioredis
from pydantic import BaseModel

from ..config import settings

# Configure logger
logger = logging.getLogger(__name__)

# Type variable for generic cache
T = TypeVar("T")


class CacheService:
    """Redis-based caching service."""

    def __init__(self):
        """Initialize the cache service with Redis connection."""
        self.redis = aioredis.from_url(settings.cache.redis_url)
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initialized Redis cache at {settings.cache.redis_url}")

    async def get(self, key: str, ttl: Optional[int] = None) -> Optional[str]:
        """Get a string value from cache.

        Args:
            key: Cache key
            ttl: If provided, reset TTL after get

        Returns:
            Cached string value or None if not found
        """
        try:
            value = await self.redis.get(key)

            if value is not None and ttl is not None:
                await self.redis.expire(key, ttl)

            return value.decode("utf-8") if value else None
        except Exception as e:
            self.logger.warning(f"Cache get failed for key '{key}': {e}")
            return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set a string value in cache.

        Args:
            key: Cache key
            value: String value to cache
            ttl: Time-to-live in seconds, if None cache won't expire

        Returns:
            True if successful, False otherwise
        """
        try:
            return await self.redis.set(key, value, ex=ttl)
        except Exception as e:
            self.logger.warning(f"Cache set failed for key '{key}': {e}")
            return False

    async def get_json(self, key: str, ttl: Optional[int] = None) -> Optional[dict]:
        """Get a JSON value from cache.

        Args:
            key: Cache key
            ttl: If provided, reset TTL after get

        Returns:
            Cached dict or None if not found
        """
        value = await self.get(key, ttl)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError as e:
                self.logger.warning(f"Failed to decode JSON for key '{key}': {e}")
        return None

    async def set_json(self, key: str, value: dict, ttl: Optional[int] = None) -> bool:
        """Set a JSON value in cache.

        Args:
            key: Cache key
            value: Dict to cache as JSON
            ttl: Time-to-live in seconds, if None cache won't expire

        Returns:
            True if successful, False otherwise
        """
        try:
            json_str = json.dumps(value)
            return await self.set(key, json_str, ttl)
        except Exception as e:
            self.logger.warning(f"Failed to encode/cache JSON for key '{key}': {e}")
            return False

    async def get_object(self, key: str, model_class: Type[T], ttl: Optional[int] = None) -> Optional[T]:
        """Get a Pydantic model from cache.

        Args:
            key: Cache key
            model_class: Pydantic model class
            ttl: If provided, reset TTL after get

        Returns:
            Cached model instance or None if not found
        """
        data = await self.get_json(key, ttl)
        if data:
            try:
                return model_class.parse_obj(data)
            except Exception as e:
                self.logger.warning(f"Failed to parse model for key '{key}': {e}")
        return None

    async def set_object(self, key: str, obj: BaseModel, ttl: Optional[int] = None) -> bool:
        """Set a Pydantic model in cache.

        Args:
            key: Cache key
            obj: Pydantic model instance
            ttl: Time-to-live in seconds, if None cache won't expire

        Returns:
            True if successful, False otherwise
        """
        try:
            return await self.set_json(key, obj.dict(), ttl)
        except Exception as e:
            self.logger.warning(f"Failed to cache model for key '{key}': {e}")
            return False

    async def get_complex(self, key: str, ttl: Optional[int] = None) -> Any:
        """Get a complex Python object from cache using pickle.

        Args:
            key: Cache key
            ttl: If provided, reset TTL after get

        Returns:
            Cached Python object or None if not found
        """
        try:
            value = await self.redis.get(key)

            if value is not None:
                if ttl is not None:
                    await self.redis.expire(key, ttl)
                return pickle.loads(value)
            return None
        except Exception as e:
            self.logger.warning(f"Complex cache get failed for key '{key}': {e}")
            return None

    async def set_complex(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a complex Python object in cache using pickle.

        Args:
            key: Cache key
            value: Python object to cache
            ttl: Time-to-live in seconds, if None cache won't expire

        Returns:
            True if successful, False otherwise
        """
        try:
            pickled = pickle.dumps(value)
            return await self.redis.set(key, pickled, ex=ttl)
        except Exception as e:
            self.logger.warning(f"Complex cache set failed for key '{key}': {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete a cached value.

        Args:
            key: Cache key

        Returns:
            True if value was deleted, False otherwise
        """
        try:
            return bool(await self.redis.delete(key))
        except Exception as e:
            self.logger.warning(f"Cache delete failed for key '{key}': {e}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern.

        Args:
            pattern: Redis key pattern (e.g., "user:*")

        Returns:
            Number of keys deleted
        """
        try:
            keys = [key async for key in self.redis.scan_iter(pattern)]
            if keys:
                return await self.redis.delete(*keys)
            return 0
        except Exception as e:
            self.logger.warning(f"Cache clear pattern failed for '{pattern}': {e}")
            return 0

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a numeric value.

        Args:
            key: Cache key
            amount: Amount to increment by

        Returns:
            New value after increment
        """
        try:
            return await self.redis.incrby(key, amount)
        except Exception as e:
            self.logger.warning(f"Cache increment failed for key '{key}': {e}")
            # If increment fails, try to set the initial value
            await self.set(key, str(amount))
            return amount

    async def get_lock(self, key: str, ttl: int = 30) -> bool:
        """Get a distributed lock.

        Args:
            key: Lock key
            ttl: Lock expiration time in seconds

        Returns:
            True if lock was acquired, False otherwise
        """
        # Use NX option to only set if key doesn't exist
        return bool(await self.redis.set(f"lock:{key}", "1", ex=ttl, nx=True))

    async def release_lock(self, key: str) -> bool:
        """Release a distributed lock.

        Args:
            key: Lock key

        Returns:
            True if lock was released, False otherwise
        """
        return await self.delete(f"lock:{key}")


# Global cache instance
cache = CacheService()
