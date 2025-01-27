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
from tqdm import tqdm

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


async def reanalyze_listings() -> None:
    """Reanalyze all listings."""
    listings = await analysis_service.get_all_listings()
    await analyze_and_save(listings)


async def resume_analysis() -> None:
    """Resume analysis of in progress listings."""
    in_progress = await analysis_service.get_in_progress_listings()
    await analyze_and_save(in_progress)


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
        completed = status_counts.get("completed", 0)
        failed = status_counts.get("failed", 0)
        pending = status_counts.get("pending", 0)
        in_progress = status_counts.get("in_progress", 0)

        # Get max retries count
        max_retries = await ListingDocument.find(
            {"retry_count": {"$gte": settings.ai.rate_limits["max_retries"]}}
        ).count()

        return {
            "total": total,
            "completed": completed,
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
    """Analyze and save listings."""
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


async def cancel_in_progress() -> int:
    """Cancel all in-progress analysis tasks.

    Returns:
        int: Number of tasks cancelled
    """
    try:
        # Get all in-progress listings
        in_progress = await analysis_service.get_in_progress_listings()
        if not in_progress:
            return 0

        # Mark them as pending to be retried later
        for listing in in_progress:
            await listing.update({"$set": {"analysis_status": AnalysisStatus.PENDING}})

        logger.info(f"Cancelled {len(in_progress)} in-progress analysis tasks")
        return len(in_progress)

    except Exception as e:
        logger.error(f"Error cancelling in-progress analyses: {str(e)}\n{traceback.format_exc()}")
        return 0


async def regenerate_embeddings() -> Dict[str, Any]:
    """Regenerate embeddings for all completed analyses."""
    try:
        # Get all completed analyses
        completed_analyses = await AnalyzedListingDocument.find_all().to_list()
        if not completed_analyses:
            return {"message": "No completed analyses found", "updated": 0}

        logger.info(f"Found {len(completed_analyses)} completed analyses to regenerate embeddings for")
        updated = 0

        # Process in batches to avoid memory issues
        batch_size = settings.scraper.batch_size["listings"]
        total_batches = (len(completed_analyses) + batch_size - 1) // batch_size

        # Create progress bars
        batch_progress = tqdm(total=total_batches, desc="Processing batches")
        item_progress = tqdm(total=len(completed_analyses), desc="Regenerating embeddings")

        for i in range(0, len(completed_analyses), batch_size):
            batch = completed_analyses[i : i + batch_size]
            logger.info(f"Processing batch {i // batch_size + 1} with {len(batch)} analyses")

            for analysis_doc in batch:
                try:
                    # Get the original listing to include its data in embedding
                    listing = await ListingDocument.get(analysis_doc.parsed_listing_id)
                    if not listing:
                        logger.warning(f"Original listing not found for analysis {analysis_doc.id}")
                        item_progress.update(1)
                        continue

                    # Generate new embeddings
                    info = {
                        "type": analysis_doc.type,
                        "brand": analysis_doc.brand,
                        "model": analysis_doc.model,
                        **analysis_doc.info,
                    }
                    embeddings = await analysis_service._generate_embeddings(info, listing)

                    # Update the document with new embeddings
                    analysis_doc.embeddings = embeddings
                    await analysis_doc.save()
                    updated += 1
                    item_progress.update(1)

                except Exception as e:
                    logger.error(f"Error regenerating embeddings for analysis {analysis_doc.id}: {str(e)}")
                    item_progress.update(1)
                    continue

            batch_progress.update(1)

        batch_progress.close()
        item_progress.close()

        return {
            "message": f"Successfully regenerated embeddings for {updated} analyses",
            "total": len(completed_analyses),
            "updated": updated,
            "dimensions": provider.get_dimensions(),
        }

    except Exception as e:
        logger.error(f"Error during embeddings regeneration: {str(e)}\n{traceback.format_exc()}")
        return {"message": f"Error during embeddings regeneration: {str(e)}", "updated": 0}
