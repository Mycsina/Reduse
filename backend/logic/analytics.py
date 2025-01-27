"""Analytics logic for listings."""

import logging
from typing import Any, Dict, List

from ..schemas.analyzed_listings import AnalyzedListingDocument

logger = logging.getLogger(__name__)


async def get_model_analytics(base_model: str) -> List[Dict[str, Any]]:
    """Get analytics for models with optional brand and model filters."""
    pipeline = [
        {
            "$lookup": {
                "from": "listings",
                "localField": "original_listing_id",
                "foreignField": "original_id",
                "as": "listing",
            }
        },
        {"$unwind": "$listing"},
        {
            "$group": {
                "_id": {"brand": "$brand", "base_model": "$base_model", "variant": "$model_variant"},
                "avg_price": {"$avg": "$listing.price_value"},
                "min_price": {"$min": "$listing.price_value"},
                "max_price": {"$max": "$listing.price_value"},
                "count": {"$sum": 1},
                "last_updated": {"$max": "$listing._id"},
            }
        },
    ]

    # Add model filter if provided
    match_conditions = {}
    if base_model:
        match_conditions["base_model"] = {"$regex": f".*{base_model}.*", "$options": "i"}

    if match_conditions:
        pipeline.insert(0, {"$match": match_conditions})

    # Format the results
    pipeline.append(
        {
            "$project": {
                "_id": 0,
                "brand": "$_id.brand",
                "base_model": "$_id.base_model",
                "variant": "$_id.variant",
                "avg_price": 1,
                "min_price": 1,
                "max_price": 1,
                "count": 1,
            }
        }
    )

    logging.debug(f"Final pipeline: {pipeline}")

    return await AnalyzedListingDocument.aggregate(pipeline).to_list()
