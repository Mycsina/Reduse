from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class SubscriptionDocument(BaseModel):
    """Model for tracking user subscriptions."""

    user_id: str
    stripe_customer_id: str
    stripe_subscription_id: Optional[str] = None
    status: str = "inactive"  # active, inactive, past_due
    current_period_end: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "stripe_customer_id": "cus_xxx",
                "stripe_subscription_id": "sub_xxx",
                "status": "active",
                "current_period_end": "2024-03-04T00:00:00Z",
                "created_at": "2024-02-04T00:00:00Z",
                "updated_at": "2024-02-04T00:00:00Z",
            }
        }
