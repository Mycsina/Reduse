from datetime import datetime
from typing import Annotated, List, Optional

from beanie import Document, Indexed
from pydantic import Field
from pymongo import GEOSPHERE, IndexModel


class FieldEmbedding(Document):
    """Stores embeddings for individual field names."""

    field_name: str = Indexed(str, unique=True)
    embedding: List[float]

    # Vector embeddings for similarity search
    embeddings: List[float] | None = None

    provider: str  # e.g., 'google', 'openai'
    model: Optional[str] = None  # e.g., 'text-embedding-ada-002'
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "field_embeddings"
        indexes = [IndexModel([("embeddings", GEOSPHERE)], name="embeddings_index")]
