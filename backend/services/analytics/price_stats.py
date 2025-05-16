"""Module for calculating and retrieving price statistics for models."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from beanie import SortDirection
from beanie.operators import RegEx

from backend.schemas.analytics import ModelPriceStats
from backend.schemas.listings import ListingDocument

logger = logging.getLogger(__name__)


async def update_model_price_stats() -> int:
    """
    Create a new snapshot of model price statistics.
    Uses the base_model field directly for grouping.

    Returns:
        int: Number of models processed.
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
                    "variants": {"$addToSet": "$analysis.model_variant"},
                }
            },
            # Filter out groups with too few listings
            {"$match": {"count": {"$gte": 3}}},  # Require at least 3 listings for statistical relevance
            # Calculate statistics
            {
                "$project": {
                    "_id": 0,
                    "base_model": "$_id",
                    "avg_price": {"$round": [{"$avg": "$prices"}, 2]},
                    "min_price": {"$round": [{"$min": "$prices"}, 2]},
                    "max_price": {"$round": [{"$max": "$prices"}, 2]},
                    "median_price": {
                        "$round": [
                            {
                                "$arrayElemAt": [
                                    "$prices",
                                    {"$floor": {"$divide": [{"$size": "$prices"}, 2]}},
                                ]
                            },
                            2,
                        ]
                    },
                    "sample_size": "$count",
                    "variants": 1,
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
                base_model = result.get("base_model")
                if not base_model:  # Skip if base_model is None
                    continue

                logger.info(f"Creating price stats for model: {base_model}")

                avg_price = result.get("avg_price")
                min_price = result.get("min_price")
                max_price = result.get("max_price")
                median_price = result.get("median_price")
                sample_size = result.get("sample_size")
                variants = result.get("variants", [])
                timestamp = result.get("timestamp")

                # Skip if any required field is None
                if any(
                    v is None
                    for v in [
                        avg_price,
                        min_price,
                        max_price,
                        median_price,
                        sample_size,
                        timestamp,
                    ]
                ):
                    logger.warning(f"Skipping incomplete stats for model {base_model}")
                    continue

                # Ensure sample_size is an integer
                if not isinstance(sample_size, (int, float, str)):
                    logger.warning(f"Invalid sample size type for model {base_model}: {type(sample_size)}")
                    continue

                try:
                    sample_size_int = int(float(str(sample_size)))
                except (TypeError, ValueError):
                    logger.warning(f"Invalid sample size for model {base_model}: {sample_size}")
                    continue

                # Filter out None values from variants
                filtered_variants = [v for v in variants if v is not None and v != ""]

                # Ensure all numeric values are properly converted to float
                safe_avg_price = float(str(avg_price))
                safe_min_price = float(str(min_price))
                safe_max_price = float(str(max_price))
                safe_median_price = float(str(median_price))

                stats.append(
                    ModelPriceStats(
                        base_model=base_model,
                        avg_price=safe_avg_price,
                        min_price=safe_min_price,
                        max_price=safe_max_price,
                        median_price=safe_median_price,
                        sample_size=sample_size_int,
                        variants=filtered_variants,
                        timestamp=(timestamp if isinstance(timestamp, datetime) else datetime.utcnow()),
                    )
                )
            except Exception as e:
                logger.error(f"Failed to create stats for model {result.get('base_model')}: {str(e)}")
                continue

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

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        logger.debug(f"Searching for price history with base_model: {base_model}")

        # Try exact match first
        results = (
            await ModelPriceStats.find(
                ModelPriceStats.base_model == base_model,
                ModelPriceStats.timestamp >= cutoff,
            )
            .sort(("timestamp", SortDirection.DESCENDING))
            .to_list()
        )

        if not results:
            logger.debug(f"No exact match found, trying case-insensitive search for: {base_model}")
            # Try case-insensitive search if exact match fails
            results = (
                await ModelPriceStats.find(
                    ModelPriceStats.base_model == RegEx(f"{base_model}", "i"),
                    ModelPriceStats.timestamp >= cutoff,
                )
                .sort(("timestamp", SortDirection.DESCENDING))
                .to_list()
            )

        if limit:
            results = results[:limit]

        logger.info(f"Retrieved {len(results)} price statistics for base model {base_model}")
        return results

    except Exception as e:
        logger.error(f"Failed to get model price history: {str(e)}")
        return []


async def get_current_model_price_stats(base_model: str) -> Optional[ModelPriceStats]:
    """
    Get the most recent price statistics for a specific model.

    Args:
        base_model: The base model to get stats for (case-insensitive)

    Returns:
        The most recent price statistics or None if no stats exist
    """
    try:
        logger.debug(f"Searching for price stats with base_model: {base_model}")
        result = (
            await ModelPriceStats.find(
                ModelPriceStats.base_model == base_model,
            )
            .sort(("timestamp", SortDirection.DESCENDING))
            .first_or_none()
        )

        if not result:
            logger.debug(f"No exact match found, trying case-insensitive search for: {base_model}")
            # Try case-insensitive search if exact match fails
            result = (
                await ModelPriceStats.find(
                    ModelPriceStats.base_model == RegEx(f"{base_model}", "i"),
                )
                .sort(("timestamp", SortDirection.DESCENDING))
                .first_or_none()
            )

        return result
    except Exception as e:
        logger.error(f"Failed to get current model price stats: {str(e)}")
        return None
