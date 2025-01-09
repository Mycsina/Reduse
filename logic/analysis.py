"""Analysis logic for product listings."""

import logging
import traceback
from typing import Any, Dict, List, Optional

from ..ai.base import AIModel
from ..ai.providers.google import GoogleAIProvider
from ..config import settings
from ..prompts.product_analysis import get_model_instance
from ..schemas.analyzed_listings import AnalyzedListingDocument
from ..schemas.listings import AnalysisStatus, ListingDocument
from ..services.analysis_service import AnalysisService

# Get logger but don't configure it (configuration is done in logging_config.py)
logger = logging.getLogger(__name__)


# Initialize AI provider and model
provider = GoogleAIProvider(settings.ai.gemini_api_key.get_secret_value())
model_config = get_model_instance()
model = AIModel(
    name=model_config.name,
    provider=provider,
    prompt_template=model_config.prompt_template,
    temperature=model_config.temperature,
    max_tokens=model_config.max_tokens,
)

# Initialize service with the model
analysis_service = AnalysisService(model)


async def add_test_listing():
    """Add a test listing to the database."""
    listing = AnalyzedListingDocument(
        original_listing_id="test_id",
        analysis_version="test_version",
        brand="test_brand",
        model="test_model",
        variant="test_variant",
        info={"test_info": "test_info"},
    )
    await listing.insert()


async def analyze_listing(listing: ListingDocument) -> Optional[AnalyzedListingDocument]:
    """Analyze a listing using the AI model."""
    try:
        result = []
        async for analyzed in analysis_service.analyze_batch([listing]):
            result.append(analyzed)
        if result:
            await change_state([listing], AnalysisStatus.COMPLETED)
            await analysis_service.bulk_create_analyses(result)
            return result[0]
        return None
    except Exception as e:
        logger.error(f"Error analyzing listing {listing.original_id}: {str(e)}")
        return None


async def analyze_new_listings() -> None:
    """Analyze pending listings."""
    pending = await analysis_service.get_pending_listings()
    if not pending:
        logger.info("No pending listings found")
        return

    logger.info(f"Found {len(pending)} unfinished listings")

    await analyze_and_save(pending)

    logger.info(f"Analysis complete: {len(pending)} listings processed")


async def retry_failed_analyses() -> None:
    """Retry failed analyses."""
    try:
        logger.info("Retrying failed analyses")
        failed_listings = await analysis_service.get_failed_listings()

        if not failed_listings:
            logger.info("No failed listings found")
            return

        logger.info(f"Found {len(failed_listings)} failed listings")

        await analyze_and_save(failed_listings)

        logger.info(f"Analysis complete: {len(failed_listings)} listings processed")

    except Exception as e:
        logger.error(f"Error retrying failed analyses: {str(e)}\n{traceback.format_exc()}")


async def get_analysis_status() -> Dict[str, Any]:
    """Get the current status of listing analysis.

    Returns:
        Dict containing analysis statistics and status
    """
    try:
        # Get status counts from service
        status_counts = await analysis_service.get_status_counts()

        # Calculate derived statistics
        total = sum(status_counts.values())
        analyzed = status_counts.get("completed", 0)
        failed = status_counts.get("failed", 0)
        pending = status_counts.get("pending", 0)
        in_progress = status_counts.get("in_progress", 0)

        # Get max retries count
        max_retries = await ListingDocument.find(
            {"retry_count": {"$gte": settings.ai.rate_limits["max_retries"]}}
        ).count()

        return {
            "total": total,
            "analyzed": analyzed,
            "pending": pending,
            "failed": failed,
            "in_progress": in_progress,
            "max_retries_reached": max_retries,
            "can_process": pending > 0 or failed > 0,
        }

    except Exception as e:
        logger.error(f"Error getting analysis status: {str(e)}")
        return {
            "error": str(e),
            "can_process": False,
        }


async def change_state(listings: List[ListingDocument], status: AnalysisStatus) -> None:
    """Change the state of listings."""
    # Collect original ids
    original_ids = [listing.original_id for listing in listings]
    # Update listings
    ListingDocument.find_many({"original_id": {"$in": original_ids}}).update({"$set": {"analysis_status": status}})


async def analyze_and_save(listings: List[ListingDocument]) -> None:
    # Collect results as they come in
    logger.debug(f"Analyzing {len(listings)} listings")
    originals = []
    analysis_results = []
    async for original, analyzed in analysis_service.analyze_batch(listings, batch_size=10):
        originals.append(original)
        analysis_results.append(analyzed)
        if len(analysis_results) >= 10:  # Save in chunks to avoid memory buildup
            logger.debug(f"Saving {len(analysis_results)} analyzed listings")
            await change_state(originals, AnalysisStatus.COMPLETED)
            await analysis_service.bulk_create_analyses(analysis_results)
            original = []
            analysis_results = []

    # Save any remaining results
    if analysis_results:
        await analysis_service.bulk_create_analyses(analysis_results)
