from beanie import Document
from datetime import datetime


class AICacheDocument(Document):
    query: str
    response: dict
    model_name: str
    created_at: datetime = datetime.utcnow()

    class Settings:
        name = "ai_cache"
        indexes = ["query", "model_name", [("created_at", -1)]]  # Descending index on created_at
