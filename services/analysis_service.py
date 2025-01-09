"""Analysis service for product listings."""

import asyncio
import logging
import traceback
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from tqdm.asyncio import tqdm

from ..ai.base import AIModel, RateLimitError
from ..prompts import product_analysis
from ..schemas.analyzed_listings import AnalyzedListingDocument
from ..schemas.listings import AnalysisStatus, ListingDocument

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self, ai_model: AIModel):
        self.ai_model = ai_model
        self.logger = logger
        self.model = product_analysis.get_model_instance()

    def parse_response(self, response: str) -> dict:
        """Parse the AI response into a structured format.

        Args:
            response: The raw response from the AI model

        Returns:
            dict: The parsed response containing listings data
        """
        try:
            import json

            return json.loads(response)
        except Exception as e:
            self.logger.error(f"Error parsing AI response: {str(e)}")
            return {"listings": []}

    async def _mark_status(self, listing: ListingDocument, status: AnalysisStatus, error: Optional[str] = None):
        """Update listing status with proper MongoDB operators."""
        update_data: Dict[str, Any] = {"$set": {"analysis_status": status.value}}
        if error:
            update_data["$set"]["analysis_error"] = error
            update_data["$inc"] = {"retry_count": 1}
        await listing.update(update_data)

    async def analyze_batch(
        self, listings: List[ListingDocument], batch_size: int = 5
    ) -> AsyncGenerator[Tuple[ListingDocument, AnalyzedListingDocument], None]:
        """Analyze listings in batches, yielding results as they're processed.

        Args:
            listings: List of listings to analyze
            batch_size: Number of listings to analyze in each batch

        Yields:
            Tuple[ListingDocument, AnalyzedListingDocument]: Original and analyzed listings
        """
        # Process listings in batches
        total_batches = (len(listings) + batch_size - 1) // batch_size
        progress_bar = tqdm(total=total_batches, desc="Analyzing listings")

        for i in range(0, len(listings), batch_size):
            batch = listings[i : i + batch_size]
            batch_num = i // batch_size + 1
            self.logger.debug(f"Processing batch {batch_num} with {len(batch)} listings")

            # Mark batch as in progress
            for listing in batch:
                await self._mark_status(listing, AnalysisStatus.IN_PROGRESS)

            # Concatenate titles and descriptions for current batch
            queries = []
            for j, listing in enumerate(batch, 1):
                title = listing.title or ""
                description = listing.description or ""
                queries.append(f"Listing {j}:\nTitle: {title}\nDescription: {description}\n---\n")

            combined_query = "\n".join(queries)

            # Make AI call for the current batch
            try:
                self.logger.debug(f"Querying model with combined query: {combined_query}")
                response = await self.ai_model.query(combined_query)
                analyzed_data = response

                # Sometimes we get the information inside a listings object
                if isinstance(analyzed_data, dict) and "listings" in analyzed_data:
                    analyzed_data = analyzed_data["listings"]

                # Process each listing in the batch
                logging.debug(f"Analyzed data: {analyzed_data}")
                for j, listing in enumerate(batch):
                    analysis = analyzed_data[j]
                    self.logger.debug(f"Analysis: {analysis}")
                    try:
                        analyzed = AnalyzedListingDocument(
                            original_listing_id=listing.original_id,
                            brand=analysis.get("brand"),
                            model=analysis.get("model"),
                            variant=analysis.get("variant"),
                            info=analysis.get("info", {}),
                            analysis_version="1.0",
                        )
                        await self._mark_status(listing, AnalysisStatus.COMPLETED)
                        yield listing, analyzed
                    except Exception as e:
                        self.logger.debug(f"Failed with analyzed data:\n{analyzed_data}")
                        self.logger.error(f"Error creating analyzed listing {j} in batch {batch_num}: {str(e)}")
                        await self._mark_status(listing, AnalysisStatus.FAILED, str(e))
                        continue
                progress_bar.update(1)

            except RateLimitError as e:
                # If we hit rate limits, mark all listings in batch as failed and retry later
                self.logger.warning(f"Rate limit exceeded, waiting {e.retry_after} seconds")
                for listing in batch:
                    await self._mark_status(listing, AnalysisStatus.FAILED, "Rate limit exceeded")
                await asyncio.sleep(e.retry_after or 60.0)
                continue

            except Exception as e:
                self.logger.error(f"Error during batch analysis: {str(e)}\n{traceback.format_exc()}")
                for listing in batch:
                    await self._mark_status(listing, AnalysisStatus.FAILED, str(e))
                continue

        progress_bar.close()

    async def get_pending_listings(self) -> List[ListingDocument]:
        """Get listings that need analysis."""
        return await ListingDocument.find({"$or": [{"analysis_status": AnalysisStatus.PENDING}]}).to_list()

    async def get_failed_listings(self) -> List[ListingDocument]:
        """Get listings that have failed analysis."""
        return await ListingDocument.find({"analysis_status": AnalysisStatus.FAILED}).to_list()

    async def get_finished_listings(self) -> List[ListingDocument]:
        """Get listings that have finished analysis."""
        return await ListingDocument.find({"analysis_status": AnalysisStatus.COMPLETED}).to_list()

    async def get_in_progress_listings(self) -> List[ListingDocument]:
        """Get listings that are in progress."""
        return await ListingDocument.find({"analysis_status": AnalysisStatus.IN_PROGRESS}).to_list()

    async def get_all_listings(self) -> List[ListingDocument]:
        """Get all listings."""
        return await ListingDocument.find({}).to_list()

    async def bulk_create_analyses(self, analyses: List[AnalyzedListingDocument]):
        """Bulk create analyses."""
        [self.logger.debug(f"Creating {analysed} in bulk") for analysed in analyses]
        self.logger.debug(analyses)
        await AnalyzedListingDocument.insert_many(analyses)

    async def get_status_counts(self) -> dict:
        """Get counts of listings in each analysis status."""
        pipeline = [{"$group": {"_id": "$analysis_status", "count": {"$sum": 1}}}]
        results = await ListingDocument.aggregate(pipeline).to_list()

        # Convert to a more friendly format and ensure all statuses are present
        counts = {status.value: 0 for status in AnalysisStatus}
        for result in results:
            if result["_id"]:  # Check if _id is not None
                counts[result["_id"]] = result["count"]

        return counts
