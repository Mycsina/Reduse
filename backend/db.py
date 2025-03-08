"""Database connection and initialization."""

import logging
from typing import Optional

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from .config import settings
from .models.analysis import AnalyzedListingDocument
from .models.batches import BatchDocument
from .models.listings import ListingDocument
from .models.schedule import ScheduleDocument
from .models.usage import UsageDocument

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Initialize the database connection and document models."""
    logger.info(f"Connecting to MongoDB: {settings.database.uri}")

    # Configure connection with improved pool settings
    client_settings = {
        "maxPoolSize": settings.database.max_pool_size,
        "minPoolSize": settings.database.min_pool_size,
        "maxIdleTimeMS": settings.database.max_idle_time_ms,
    }

    client = AsyncIOMotorClient(settings.database.uri, **client_settings)

    # Add health check function to client for monitoring
    client.get_io_loop = lambda: None  # Workaround for event loop issues

    logger.info(f"Initializing Beanie with database: {settings.database.database_name}")

    # Initialize document models
    document_models = [
        ListingDocument,
        AnalyzedListingDocument,
        BatchDocument,
        ScheduleDocument,
        UsageDocument,
    ]

    try:
        await init_beanie(
            database=client[settings.database.database_name],
            document_models=document_models,
        )
        logger.info("Database initialization successful")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def get_client() -> AsyncIOMotorClient:
    """Get the MongoDB client.

    Returns:
        AsyncIOMotorClient: The MongoDB client
    """
    return AsyncIOMotorClient(settings.database.uri)


async def check_connection() -> bool:
    """Check if the database connection is healthy.

    Returns:
        bool: True if connection is healthy, False otherwise
    """
    try:
        client = AsyncIOMotorClient(
            settings.database.uri,
            serverSelectionTimeoutMS=5000,
        )
        await client.admin.command("ping")
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False
