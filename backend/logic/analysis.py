"""Analysis logic for product listings."""

import logging
import traceback
from typing import Any, Dict, List, Optional

from tqdm import tqdm

from ..ai.providers.factory import create_provider
from ..config import PROVIDER_TYPE, settings
from ..schemas.analysis import AnalysisStats, AnalyzedListingDocument
from ..schemas.listings import AnalysisStatus, ListingDocument
from ..services.analysis import (_generate_listing_embeddings, analyze_batch,
                                 bulk_create_analyses, get_listings_by_status,
                                 get_status_counts)
from ..services.query import get_distinct_info_fields

# Get logger but don't configure it (configuration is done in logging_config.py)
logger = logging.getLogger(__name__)
provider = create_provider(PROVIDER_TYPE.GROQ, model="llama-3.2-3b-preview")


async def analyze_listing(
    listing: ListingDocument,
) -> Optional[AnalyzedListingDocument]:
    """Analyze a listing using the AI model."""
    try:
        # Get existing fields from the database
        existing_fields = await get_distinct_info_fields()

        result = []
        async for analyzed in analyze_batch([listing], existing_fields=existing_fields):
            result.append(analyzed)
        if result:
            await change_state([listing], AnalysisStatus.COMPLETED)
            await bulk_create_analyses(result)
            return result[0]
        return None
    except Exception as e:
        logger.error(f"Error analyzing listing {listing.original_id}: {str(e)}")
        return None


async def analyze_new_listings() -> None:
    """Analyze pending listings."""
    pending = await get_listings_by_status(AnalysisStatus.PENDING)
    if not pending:
        logger.info("No pending listings found")
        return

    logger.info(f"Found {len(pending)} unfinished listings")

    # Get existing fields once for all listings
    existing_fields = await get_distinct_info_fields()
    logger.info(f"Found {len(existing_fields)} existing fields to consider")

    await analyze_and_save(pending, existing_fields=existing_fields)

    logger.info(f"Analysis complete: {len(pending)} listings processed")


async def retry_failed_analyses() -> None:
    """Retry failed analyses."""
    try:
        logger.info("Retrying failed analyses")
        failed_listings = await get_listings_by_status(AnalysisStatus.FAILED)

        if not failed_listings:
            logger.info("No failed listings found")
            return

        logger.info(f"Found {len(failed_listings)} failed listings")

        # Get existing fields once for all listings
        existing_fields = await get_distinct_info_fields()
        logger.info(f"Found {len(existing_fields)} existing fields to consider")

        await analyze_and_save(failed_listings, existing_fields=existing_fields)

        logger.info(f"Analysis complete: {len(failed_listings)} listings processed")

    except Exception as e:
        logger.error(
            f"Error retrying failed analyses: {str(e)}\n{traceback.format_exc()}"
        )


async def reanalyze_listings() -> None:
    """Reanalyze all listings."""
    listings = await get_listings_by_status(AnalysisStatus.COMPLETED)
    existing_fields = await get_distinct_info_fields()
    await analyze_and_save(listings, existing_fields=existing_fields)


async def resume_analysis() -> None:
    """Resume analysis of in progress listings."""
    in_progress = await get_listings_by_status(AnalysisStatus.IN_PROGRESS)
    existing_fields = await get_distinct_info_fields()
    await analyze_and_save(in_progress, existing_fields=existing_fields)


async def get_analysis_status() -> AnalysisStats:
    """Get the current status of listing analysis.

    Returns:
        Dict containing analysis statistics and status
    """
    try:
        # Get status counts from service
        status_counts = await get_status_counts()

        # Calculate derived statistics
        total = sum(status_counts.values())
        completed = status_counts.get("completed", 0)
        failed = status_counts.get("failed", 0)
        pending = status_counts.get("pending", 0)
        in_progress = status_counts.get("in_progress", 0)

        # Get max retries count
        max_retries = await ListingDocument.find(
            {"retry_count": {"$gte": 3}}
        ).count()  # Default to 3 retries

        return AnalysisStats(
            total=total,
            completed=completed,
            pending=pending,
            failed=failed,
            in_progress=in_progress,
            max_retries_reached=max_retries,
        )

    except Exception as e:
        logger.error(f"Error getting analysis status: {str(e)}")
        return AnalysisStats(
            total=0,
            completed=0,
            pending=0,
            failed=0,
            in_progress=0,
            max_retries_reached=0,
        )


async def change_state(listings: List[ListingDocument], status: AnalysisStatus) -> None:
    """Change the state of listings."""
    # Collect original ids
    original_ids = [listing.original_id for listing in listings]
    # Update listings
    ListingDocument.find_many({"original_id": {"$in": original_ids}}).update(
        {"$set": {"analysis_status": status}}
    )


async def analyze_and_save(
    listings: List[ListingDocument], existing_fields: Optional[List[str]] = None
) -> None:
    """Analyze and save listings."""
    # Collect results as they come in
    logger.debug(f"Analyzing {len(listings)} listings")
    originals = []
    analysis_results = []
    async for original, analyzed in analyze_batch(
        listings, batch_size=10, existing_fields=existing_fields
    ):
        originals.append(original)
        analysis_results.append(analyzed)
        if len(analysis_results) >= 10:  # Save in chunks to avoid memory buildup
            logger.debug(f"Saving {len(analysis_results)} analyzed listings")
            await change_state(originals, AnalysisStatus.COMPLETED)
            await bulk_create_analyses(analysis_results)
            originals = []
            analysis_results = []

    # Save any remaining results
    if analysis_results:
        await bulk_create_analyses(analysis_results)


async def cancel_in_progress() -> int:
    """Cancel all in-progress analysis tasks.

    Returns:
        int: Number of tasks cancelled
    """
    try:
        # Get all in-progress listings
        in_progress = await get_listings_by_status(AnalysisStatus.IN_PROGRESS)
        if not in_progress:
            return 0

        # Mark them as pending to be retried later
        for listing in in_progress:
            await listing.update({"$set": {"analysis_status": AnalysisStatus.PENDING}})

        logger.info(f"Cancelled {len(in_progress)} in-progress analysis tasks")
        return len(in_progress)

    except Exception as e:
        logger.error(
            f"Error cancelling in-progress analyses: {str(e)}\n{traceback.format_exc()}"
        )
        return 0


async def regenerate_embeddings() -> Dict[str, Any]:
    """Regenerate embeddings for all completed analyses."""
    try:
        # Get all completed analyses
        completed_analyses = await AnalyzedListingDocument.find_all().to_list()
        if not completed_analyses:
            return {"message": "No completed analyses found", "updated": 0}

        logger.info(
            f"Found {len(completed_analyses)} completed analyses to regenerate embeddings for"
        )
        updated = 0

        # Process in batches to avoid memory issues
        batch_size = settings.scraper.batch_size["listings"]
        total_batches = (len(completed_analyses) + batch_size - 1) // batch_size

        # Create progress bars
        batch_progress = tqdm(total=total_batches, desc="Processing batches")
        item_progress = tqdm(
            total=len(completed_analyses), desc="Regenerating embeddings"
        )

        for i in range(0, len(completed_analyses), batch_size):
            batch = completed_analyses[i : i + batch_size]
            logger.info(
                f"Processing batch {i // batch_size + 1} with {len(batch)} analyses"
            )

            for analysis_doc in batch:
                try:
                    # Get the original listing to include its data in embedding
                    listing = await ListingDocument.get(analysis_doc.parsed_listing_id)
                    if not listing:
                        logger.warning(
                            f"Original listing not found for analysis {analysis_doc.id}"
                        )
                        item_progress.update(1)
                        continue

                    # Generate new embeddings
                    info = {
                        "type": analysis_doc.type,
                        "brand": analysis_doc.brand,
                        "model": analysis_doc.model,
                        **analysis_doc.info,
                    }
                    embeddings = await _generate_listing_embeddings(info, listing)

                    # Update the document with new embeddings
                    analysis_doc.embeddings = embeddings
                    await analysis_doc.save()
                    updated += 1
                    item_progress.update(1)

                except Exception as e:
                    logger.error(
                        f"Error regenerating embeddings for analysis {analysis_doc.id}: {str(e)}"
                    )
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
        logger.error(
            f"Error during embeddings regeneration: {str(e)}\n{traceback.format_exc()}"
        )
        return {
            "message": f"Error during embeddings regeneration: {str(e)}",
            "updated": 0,
        }
