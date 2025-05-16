"""Schema definitions for favorite searches."""

from datetime import datetime
from typing import List, Optional

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, ConfigDict, Field

from .filtering import SavedListingQueryItems  # Updated import


class FavoriteSearchBase(BaseModel):
    """Base model for favorite search data."""

    name: str = Field(..., description="User-defined name for the favorite search")
    query_params: SavedListingQueryItems = Field(  # Updated type
        ..., description="The structured query parameters for this favorite search"
    )


class FavoriteSearchCreate(FavoriteSearchBase):
    """Model for creating a new favorite search."""

    pass


class FavoriteSearchUpdate(BaseModel):
    """Model for updating a favorite search (e.g., renaming)."""

    name: Optional[str] = Field(None, description="New name for the favorite search")


class FavoriteSearchRead(FavoriteSearchBase):
    """Model for reading favorite search data, including ID and metadata."""

    id: PydanticObjectId = Field(..., alias="_id")
    user_id: PydanticObjectId
    created_at: datetime
    last_viewed_at: Optional[datetime] = None
    seen_listing_ids: List[PydanticObjectId] = Field(default_factory=list)
    new_listings_count: int = Field(
        0, description="Number of new listings for this favorite since last viewed"
    )

    model_config = ConfigDict(
        populate_by_name=True,  # Allow using alias _id
        json_encoders={PydanticObjectId: str},  # Ensure IDs are serialized as strings
        from_attributes=True,  # Allow populating from object attributes
    )


class FavoriteSearchDocument(Document, FavoriteSearchBase):
    """MongoDB document model for favorite searches."""

    user_id: PydanticObjectId  # Define the field type
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_viewed_at: Optional[datetime] = Field(None)
    seen_listing_ids: List[PydanticObjectId] = Field(default_factory=list)

    class Settings:
        name = "favorite_searches"
        indexes = [
            [("user_id", 1)],  # Explicitly define the index here
        ]
