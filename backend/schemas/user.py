"""Schema for user data."""

from datetime import datetime
from typing import Annotated

from beanie import Document, Indexed
from pydantic import Field


class UserDocument(Document):
    """Schema for user data."""

    api_key: Annotated[str, Indexed(unique=True)]
    is_premium: bool = False
    is_admin: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "users"
        indexes = [
            [("api_key", 1)],  # For API key lookups
            [("is_premium", 1)],  # For premium user queries
            [("is_admin", 1)],  # For admin user queries
            [("created_at", -1)],  # For sorting by creation date
        ]
