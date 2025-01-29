"""Schema for AI response caching."""

from datetime import datetime
from typing import Annotated

from beanie import Document, Indexed


class AICacheDocument(Document):
    """Document for caching AI responses to avoid duplicate queries."""

    query: Annotated[str, Indexed()]
    response: dict
    model_name: Annotated[str, Indexed()]
    created_at: Annotated[datetime, Indexed()] = datetime.utcnow()

    class Settings:
        name = "ai_cache"
