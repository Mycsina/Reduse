"""Analysis logic for product listings."""

import asyncio
import logging
import traceback
from typing import Any, Dict, List, Optional, Tuple

from beanie import PydanticObjectId
from tqdm import tqdm

from backend.ai.providers.factory import create_provider
from backend.config import PROVIDER_TYPE, settings
from backend.schemas.analysis import AnalysisStats, AnalyzedListingDocument
from backend.schemas.listings import AnalysisStatus, ListingDocument
from backend.services.analysis import (_generate_listing_embeddings,
                                       analyze_batch, bulk_create_analyses,
                                       get_listings_by_status,
                                       get_status_counts)
from backend.services.query import get_distinct_info_fields

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
    await ListingDocument.find_many({"original_id": {"$in": original_ids}}).update_many(
        {"$set": {"analysis_status": status.value}}
    )


async def analyze_and_save(
    listings: List[ListingDocument],
    existing_fields: Optional[List[str]] = None,
) -> None:
    """Analyze and save listings.
    Uses a progress bar to track overall progress.
    Concurrency is controlled by settings.ai.analysis_max_concurrent.
    """
    # Get concurrency setting for logging
    max_concurrent = settings.ai.analysis_max_concurrent
    # Collect results as they come in
    logger.debug(
        f"Analyzing {len(listings)} listings with max concurrency {max_concurrent}"
    )
    originals = []
    analysis_results = []
    save_chunk_size = 10  # Define chunk size for saving

    # Use tqdm for the main loop
    progress_bar = tqdm(total=len(listings), desc="Analyzing and saving listings")

    async for original, analyzed in analyze_batch(
        listings,
        batch_size=10,
        existing_fields=existing_fields,  # Removed max_concurrent param
    ):
        originals.append(original)
        analysis_results.append(analyzed)
        progress_bar.update(1)  # Update progress for each analyzed item

        if len(analysis_results) >= save_chunk_size:  # Save in chunks
            logger.debug(f"Saving {len(analysis_results)} analyzed listings")
            # Mark as completed *before* saving analysis docs to avoid potential race conditions
            # If saving fails, the listings remain COMPLETED, which is acceptable for retry logic.
            await change_state(originals, AnalysisStatus.COMPLETED)
            await bulk_create_analyses(analysis_results)
            originals = []
            analysis_results = []

    # Save any remaining results
    if analysis_results:
        logger.debug(f"Saving final {len(analysis_results)} analyzed listings")
        await change_state(originals, AnalysisStatus.COMPLETED)
        await bulk_create_analyses(analysis_results)

    progress_bar.close()


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


async def _regenerate_single_embedding(
    analysis_doc: AnalyzedListingDocument,
    semaphore: asyncio.Semaphore,
) -> Tuple[Optional[PydanticObjectId], Optional[List[float]], Optional[Exception]]:
    """Helper function to regenerate embedding for a single analysis document."""
    async with semaphore:
        try:
            # Get the original listing to include its data in embedding
            listing = await ListingDocument.get(analysis_doc.parsed_listing_id)
            if not listing:
                logger.warning(
                    f"Original listing not found for analysis {analysis_doc.id}"
                )
                return (
                    analysis_doc.id,
                    None,
                    None,
                )  # Return ID but no embedding or error

            # Prepare info for embedding generation
            info = {
                "type": analysis_doc.type,
                "brand": analysis_doc.brand,
                # Ensure base_model and model_variant exist before accessing them
                "base_model": getattr(analysis_doc, "base_model", None),
                "model_variant": getattr(analysis_doc, "model_variant", None),
                **analysis_doc.info,
            }
            # Filter out None values from info before passing to embedding function
            info = {k: v for k, v in info.items() if v is not None}

            # Generate new embeddings
            embeddings = await _generate_listing_embeddings(info, listing)

            return analysis_doc.id, embeddings, None

        except Exception as e:
            logger.error(
                f"Error regenerating embeddings for analysis {analysis_doc.id}: {str(e)}"
            )
            return analysis_doc.id, None, e


async def regenerate_embeddings(
    max_concurrency=settings.ai.embedding_max_concurrent,
) -> Dict[str, Any]:
    """Regenerate embeddings for all completed analyses concurrently.
    Concurrency is controlled by settings.ai.embedding_max_concurrent.
    """
    try:
        # Get all completed analyses
        completed_analyses = await AnalyzedListingDocument.find(
            AnalyzedListingDocument.embeddings
            != None  # Fetch only those that presumably have embeddings
        ).to_list()

        if not completed_analyses:
            return {
                "message": "No completed analyses with existing embeddings found",
                "updated": 0,
            }

        logger.info(
            f"Found {len(completed_analyses)} completed analyses to regenerate embeddings for"
        )

        # Read concurrency limit from settings
        semaphore = asyncio.Semaphore(max_concurrency)

        tasks = [
            _regenerate_single_embedding(analysis_doc, semaphore)
            for analysis_doc in completed_analyses
        ]

        updated = 0
        failed_ids = []
        updated_embeddings = {}

        # Use tqdm for tracking progress of gathering results
        progress_bar = tqdm(total=len(tasks), desc="Regenerating embeddings")

        # Process results as they complete
        for future in asyncio.as_completed(tasks):
            doc_id, embeddings, error = await future
            if error:
                logger.error(f"Failed to regenerate embedding for {doc_id}: {error}")
                if doc_id:
                    failed_ids.append(doc_id)
            elif doc_id and embeddings:
                updated_embeddings[doc_id] = embeddings
                updated += 1
            progress_bar.update(1)

        progress_bar.close()

        # Bulk update the embeddings in the database
        if updated_embeddings:
            logger.info(
                f"Bulk updating embeddings for {len(updated_embeddings)} analyses."
            )

            # Iterative saving approach
            update_progress = tqdm(
                total=len(updated_embeddings), desc="Saving updated embeddings"
            )
            for doc_id, embeddings_list in updated_embeddings.items():
                # Ensure doc_id is a valid PydanticObjectId if needed, although .get should handle it
                doc = await AnalyzedListingDocument.get(doc_id)
                if doc:
                    doc.embeddings = embeddings_list
                    await doc.save()
                update_progress.update(1)
            update_progress.close()
            logger.info(f"Finished saving updated embeddings.")

        result_message = f"Successfully regenerated embeddings for {updated} analyses."
        if failed_ids:
            result_message += f" Failed for {len(failed_ids)} analyses."

        return {
            "message": result_message,
            "total_processed": len(completed_analyses),
            "updated": updated,
            "failed": len(failed_ids),
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
