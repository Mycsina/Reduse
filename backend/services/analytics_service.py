import logging
from datetime import datetime, timedelta
from typing import List, Optional

from beanie.operators import RegEx

from ..schemas.analytics import ModelPriceStats
from ..schemas.listings import ListingDocument


logger = logging.getLogger(__name__)


async def update_model_price_stats() -> int:
    """
    Create a new snapshot of model price statistics.
    Returns the number of models processed.
    """
    try:
        pipeline = [
            # Match only listings with valid prices
            {
                "$match": {
                    "price_value": {"$exists": True, "$ne": None, "$gt": 0},
                    "analysis_status": "completed",  # Only use analyzed listings
                }
            },
            {
                "$lookup": {
                    "from": "analyzed_listings",
                    "localField": "original_id",
                    "foreignField": "original_listing_id",
                    "as": "analysis",
                }
            },
            {"$unwind": "$analysis"},
            # Filter out listings without base_model
            {"$match": {"analysis.base_model": {"$exists": True, "$nin": [None, ""]}}},
            {
                "$group": {
                    "_id": "$analysis.base_model",
                    "prices": {"$push": {"$toDouble": "$price_value"}},
                    "count": {"$sum": 1},
                }
            },
            # Filter out groups with too few listings
            {"$match": {"count": {"$gte": 3}}},  # Require at least 3 listings for statistical relevance
            # Calculate statistics
            {
                "$project": {
                    "_id": 0,
                    "model": "$_id",  # Keep field name as model for compatibility
                    "avg_price": {"$round": [{"$avg": "$prices"}, 2]},
                    "min_price": {"$round": [{"$min": "$prices"}, 2]},
                    "max_price": {"$round": [{"$max": "$prices"}, 2]},
                    "median_price": {
                        "$round": [{"$arrayElemAt": ["$prices", {"$floor": {"$divide": [{"$size": "$prices"}, 2]}}]}, 2]
                    },
                    "sample_size": "$count",
                    "timestamp": {"$literal": datetime.utcnow()},
                }
            },
        ]

        results = await ListingDocument.aggregate(pipeline).to_list()

        if not results:
            logger.warning("No price statistics generated - no valid data found")
            return 0

        stats = []
        for result in results:
            try:
                logger.debug(f"Appending: {result}")
                stats.append(ModelPriceStats(**result))
            except Exception as e:
                logger.error(f"Failed to create stats for model {result.get('model')}: {str(e)}")
                raise e

        if stats:
            await ModelPriceStats.insert_many(stats)
            logger.info(f"Created price statistics for {len(stats)} models")
            return len(stats)
        return 0

    except Exception as e:
        logger.error(f"Failed to update model price statistics: {str(e)}")
        raise e


async def get_model_price_history(
    base_model: str, days: int = 30, limit: Optional[int] = None
) -> List[ModelPriceStats]:
    """
    Get price history for a specific model.

    Args:
        base_model: The base model name (case-insensitive)
        days: Number of days of history to retrieve
        limit: Optional limit on number of results

    Returns:
        List of price statistics ordered by timestamp
    """
    try:
        if not base_model:
            logger.error("Base model must be provided")
            return []

        if days < 1:
            logger.error("Days must be positive")
            return []

        cutoff = datetime.utcnow() - timedelta(days=days)
        query = {"model": RegEx(f"^{base_model}$", "i"), "timestamp": {"$gte": cutoff}}

        logger.debug(f"Querying for model price history: {query}")
        find_query = ModelPriceStats.find(query).sort("timestamp")
        if limit:
            find_query = find_query.limit(limit)

        results = await find_query.to_list()
        logger.info(f"Retrieved {len(results)} price statistics for base model {base_model}")
        return results

    except Exception as e:
        logger.error(f"Failed to get model price history: {str(e)}")
        return []
