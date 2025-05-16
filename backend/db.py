"""Database connection and initialization."""

import logging

from beanie import init_beanie
from fastapi_users.db import BeanieUserDatabase
from motor.motor_asyncio import AsyncIOMotorClient

from backend.config import settings
from backend.schemas.analysis import AnalyzedListingDocument
from backend.schemas.analytics import FieldValueStats, ModelPriceStats
from backend.schemas.batch import BatchJobDocument
from backend.schemas.bug_reports import BugReportDocument
from backend.schemas.embeddings import FieldEmbedding
from backend.schemas.favorites import FavoriteSearchDocument
from backend.schemas.field_harmonization import FieldHarmonizationMapping
from backend.schemas.listings import ListingDocument
from backend.schemas.users import User

logger = logging.getLogger(__name__)


async def get_user_db():
    yield BeanieUserDatabase(User)  # type: ignore


async def init_db() -> None:
    """Initialize the database connection and document models."""
    logger.info(f"Connecting to MongoDB: {settings.database.uri}")

    client = AsyncIOMotorClient(settings.database.uri)

    logger.info(f"Initializing Beanie with database: {settings.database.database_name}")

    document_models = [
        ListingDocument,
        AnalyzedListingDocument,
        BatchJobDocument,
        BugReportDocument,
        FieldEmbedding,
        FieldHarmonizationMapping,
        ModelPriceStats,
        FieldValueStats,
        User,
        FavoriteSearchDocument,
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
