import os

from beanie import init_beanie
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from .schemas.listings import ListingDocument
from .schemas.analyzed_listings import AnalyzedListingDocument
from .schemas.ai_cache import AICacheDocument

load_dotenv(override=True)
ATLAS_USER = os.getenv("ATLAS_USER")
ATLAS_PASS = os.getenv("ATLAS_PASSWORD")


URI = f"mongodb+srv://{ATLAS_USER}:{ATLAS_PASS}@vroom.k7x4g.mongodb.net/?retryWrites=true&w=majority&appName=vroom"


async def init_db():
    client = AsyncIOMotorClient(URI)
    db_name = client.get_database("Vroom")
    await init_beanie(database=db_name, document_models=[ListingDocument, AnalyzedListingDocument, AICacheDocument])
