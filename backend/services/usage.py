"""Usage tracking service."""

from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Dict


async def get_daily_usage(db: AsyncIOMotorDatabase, user_id: str, feature: str) -> Dict[str, int]:
    """Get user's feature usage for the last 24 hours.
    
    Args:
        db: Database instance
        user_id: The ID of the user to check
        feature: The feature to check usage for
        
    Returns:
        dict: Usage statistics including used count, remaining uses, and limits
    """
    start_time = datetime.utcnow() - timedelta(hours=24)

    pipeline = [
        {"$match": {"user_id": user_id, "feature": feature, "date": {"$gte": start_time}}},
        {"$group": {"_id": None, "total_count": {"$sum": "$count"}}},
    ]

    result = await db.usage.aggregate(pipeline).to_list(1)
    total_uses = result[0]["total_count"] if result else 0

    return {"used": total_uses, "remaining": max(0, 10 - total_uses), "limit": 10, "is_limited": total_uses >= 10}


async def check_usage(db: AsyncIOMotorDatabase, user_id: str, feature: str) -> Dict[str, int]:
    """Check if a user has remaining usage for a feature.
    
    Args:
        db: Database instance
        user_id: The ID of the user to check
        feature: The feature to check usage for
        
    Returns:
        dict: Usage statistics including remaining uses
    """
    return await get_daily_usage(db, user_id, feature)


async def record_usage(db: AsyncIOMotorDatabase, user_id: str, feature: str) -> bool:
    """Record a usage of a feature.
    
    Args:
        db: Database instance
        user_id: The ID of the user
        feature: The feature being used
        
    Returns:
        bool: True if usage was recorded, False if limit reached
    """
    usage = await get_daily_usage(db, user_id, feature)

    if usage["is_limited"]:
        return False

    today = datetime.utcnow().date()
    await db.usage.update_one(
        {"user_id": user_id, "feature": feature, "date": today}, {"$inc": {"count": 1}}, upsert=True
    )

    return True


async def reset_daily_usage(db: AsyncIOMotorDatabase) -> None:
    """Reset usage counts older than 24 hours.
    
    Args:
        db: Database instance
    """
    cutoff = datetime.utcnow() - timedelta(hours=24)
    await db.usage.delete_many({"date": {"$lt": cutoff}})
