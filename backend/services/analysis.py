"""Analysis service for product listings."""

import asyncio
import json
import logging
import traceback
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from tqdm.asyncio import tqdm

from ..ai.prompts.product_analysis import create_product_analysis_prompt
from ..ai.providers.factory import create_provider
from ..config import PROVIDER_TYPE
from ..schemas.analysis import AnalyzedListingDocument
from ..schemas.listings import AnalysisStatus, ListingDocument
from ..utils.errors import RateLimitError

logger = logging.getLogger(__name__)
provider = create_provider(PROVIDER_TYPE.GROQ, model="llama-3.2-3b-preview")


async def _generate_listing_embeddings(
    info: Dict[str, Any], listing: ListingDocument
) -> List[float]:
    """Generate embeddings from the listing and its analysis info.

    Prioritizes type, brand, and model information in the embedding text representation.
    Other fields are included with less emphasis.

    Args:
        info: Analyzed information about the listing
        listing: Original listing document

    Returns:
        Vector embeddings for the listing
    """
    # Core identity parts (repeated for emphasis)
    core_parts = []
    for key in ["type", "brand", "base_model", "model_variant"]:
        if value := info.get(key):
            # Repeat core information to increase its weight in embeddings
            core_parts.extend([f"{key}: {value}"] * 3)

    # Start with title and core identity
    text_parts = [f"title: {listing.title}", *core_parts]

    # Add other analyzed info with less emphasis
    other_parts = []
    for key, value in sorted(info.items()):
        if key not in [
            "type",
            "brand",
            "base_model",
            "model_variant",
        ]:  # Skip core fields as they're already included
            if isinstance(value, (list, tuple)):
                other_parts.append(f"{key}: {', '.join(str(v) for v in value)}")
            elif isinstance(value, dict):
                other_parts.append(
                    f"{key}: {', '.join(f'{k}={v}' for k, v in sorted(value.items()))}"
                )
            else:
                other_parts.append(f"{key}: {value}")

    # Combine all parts, with core information at the start
    text = " | ".join(text_parts + other_parts)
    logger.debug(
        f"Generated embedding text for listing {listing.original_id}: {text[:200]}..."
    )

    # Get embeddings from provider
    embeddings = await provider.get_embeddings([text])
    return embeddings[0]  # Return first (and only) vector


def parse_response(response: str) -> dict:
    """Parse the AI response into a structured format."""
    try:
        return json.loads(response)
    except Exception as e:
        logger.error(f"Error parsing AI response: {str(e)}")
        return {"listings": []}


async def _mark_status(
    listing: ListingDocument,
    status: AnalysisStatus,
    error: Optional[str] = None,
):
    """Update listing status with proper MongoDB operators."""
    update_data: Dict[str, Any] = {"$set": {"analysis_status": status.value}}
    if error:
        update_data["$set"]["analysis_error"] = error
        update_data["$inc"] = {"retry_count": 1}
    await listing.update(update_data)


async def analyze_batch(
    listings: List[ListingDocument],
    batch_size: int = 5,
    existing_fields: Optional[List[str]] = None,
) -> AsyncGenerator[Tuple[ListingDocument, AnalyzedListingDocument], None]:
    """Analyze listings in batches, yielding results as they're processed.

    Args:
        listings: List of listings to analyze
        batch_size: Number of listings to process in each batch
        existing_fields: List of existing field names to consider for reuse
    """
    # Process listings in batches
    total_batches = (len(listings) + batch_size - 1) // batch_size
    progress_bar = tqdm(total=total_batches, desc="Analyzing listings")

    for i in range(0, len(listings), batch_size):
        batch = listings[i : i + batch_size]
        batch_num = i // batch_size + 1
        logger.debug(f"Processing batch {batch_num} with {len(batch)} listings")

        # Mark batch as in progress
        for listing in batch:
            await _mark_status(listing, AnalysisStatus.IN_PROGRESS)

        # Process each listing in the batch
        for listing in batch:
            try:
                # Create prompt for this listing
                input_text = f"Title: {listing.title or ''}\nDescription: {listing.description or ''}"
                prompt = create_product_analysis_prompt().format(
                    input=input_text, existing_fields=existing_fields
                )

                # Make AI call for the current listing
                logger.debug(f"Querying model for listing {listing.original_id}")
                analysis = await provider.generate_json(
                    prompt,
                )

                # Generate embeddings from the info struct
                info = analysis.get("info", {})

                # If field is a comma separated string, split it into a list
                for key, value in info.items():
                    if isinstance(value, str):
                        info[key] = value.split(",")

                embeddings = await _generate_listing_embeddings(info, listing)

                analyzed = AnalyzedListingDocument(
                    parsed_listing_id=listing.id,
                    original_listing_id=listing.original_id,
                    type=analysis.get("type"),
                    brand=analysis.get("brand"),
                    base_model=analysis.get("base_model"),
                    model_variant=analysis.get("model_variant"),
                    info=info,
                    embeddings=embeddings,
                    analysis_version="1.0",
                )
                await _mark_status(listing, AnalysisStatus.COMPLETED)
                yield listing, analyzed

            except RateLimitError as e:
                logger.warning(f"Rate limit exceeded, waiting {e.retry_after} seconds")
                await _mark_status(
                    listing, AnalysisStatus.FAILED, "Rate limit exceeded"
                )
                await asyncio.sleep(e.retry_after or 60.0)
                continue

            except Exception as e:
                logger.error(
                    f"Error analyzing listing {listing.original_id}: {str(e)}\n{traceback.format_exc()}"
                )
                await _mark_status(listing, AnalysisStatus.FAILED, str(e))
                continue

        progress_bar.update(1)

    progress_bar.close()


async def get_listings_by_status(status: AnalysisStatus) -> List[ListingDocument]:
    """Get listings by status."""
    return await ListingDocument.find({"analysis_status": status.value}).to_list()


async def get_all_listings() -> List[ListingDocument]:
    """Get all listings."""
    return await ListingDocument.find({}).to_list()


async def bulk_create_analyses(analyses: List[AnalyzedListingDocument]):
    """Bulk create analyses."""
    [
        logger.debug(f"Creating {analysed.original_listing_id} in bulk")
        for analysed in analyses
    ]
    original_ids = [analysed.original_listing_id for analysed in analyses]
    [logger.debug(f"Deleting {original_id}") for original_id in original_ids]
    await AnalyzedListingDocument.find_many(
        {"original_listing_id": {"$in": original_ids}}
    ).delete()
    await AnalyzedListingDocument.insert_many(analyses)


async def get_status_counts() -> dict:
    """Get counts of listings in each analysis status."""
    pipeline = [{"$group": {"_id": "$analysis_status", "count": {"$sum": 1}}}]
    results = await ListingDocument.aggregate(pipeline).to_list()

    # Convert to a more friendly format and ensure all statuses are present
    counts = {status.value: 0 for status in AnalysisStatus}
    for result in results:
        if result["_id"]:  # Check if _id is not None
            counts[result["_id"]] = result["count"]

    return counts
