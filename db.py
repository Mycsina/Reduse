"""Database initialization and configuration."""

import logging
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from .config import settings
from .schemas.ai_cache import AICacheDocument
from .schemas.analyzed_listings import AnalyzedListingDocument
from .schemas.listings import ListingDocument

logger = logging.getLogger(__name__)

# List of document models to register with Beanie
MODELS = [ListingDocument, AnalyzedListingDocument, AICacheDocument]


async def init_db():
    """Initialize the database connection and Beanie ODM."""
    logger.info("Initializing database")
    client = AsyncIOMotorClient(settings.database.uri)
    await init_beanie(database=client.get_database(settings.database.database_name), document_models=MODELS)
    logger.info("Database initialized")


def get_db():
    """Get a database client instance."""
    return AsyncIOMotorClient(settings.database.uri)
