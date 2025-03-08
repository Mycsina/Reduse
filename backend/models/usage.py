from datetime import datetime
from pydantic import BaseModel, Field


class UsageDocument(BaseModel):
    """Model for tracking feature usage."""

    user_id: str
    feature: str
    date: datetime = Field(default_factory=datetime.utcnow)
    count: int = Field(default=1, ge=0)

    class Config:
        json_schema_extra = {
            "example": {"user_id": "user123", "feature": "price_history", "date": "2024-02-04T00:00:00Z", "count": 5}
        }
