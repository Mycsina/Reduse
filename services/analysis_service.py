"""Analysis service for product listings."""

import logging
from typing import List, AsyncGenerator
from tqdm.asyncio import tqdm

from ..ai.base import AIModel
from ..prompts import product_analysis
from ..schemas.analyzed_listings import AnalyzedListingDocument
from ..schemas.listings import AnalysisStatus, ListingDocument

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self, ai_model: AIModel):
        self.ai_model = ai_model
        self._backoff_base = 2
        self._max_backoff = 300  # 5 minutes
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

    async def analyze_batch(
        self, listings: List[ListingDocument], batch_size: int = 5
    ) -> AsyncGenerator[AnalyzedListingDocument, None]:
        """Analyze listings in batches, yielding results as they're processed.

        Args:
            listings: List of listings to analyze
            batch_size: Number of listings to analyze in each batch

        Yields:
            AnalyzedListingDocument: Analyzed listings one at a time
        """
        # Process listings in batches
        total_batches = (len(listings) + batch_size - 1) // batch_size
        progress_bar = tqdm(total=total_batches, desc="Analyzing listings")

        for i in range(0, len(listings), batch_size):
            batch = listings[i : i + batch_size]
            batch_num = i // batch_size + 1
            self.logger.debug(f"Processing batch {batch_num} with {len(batch)} listings")

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

                # Process each listing in the batch
                for j, listing in enumerate(batch):
                    analysis = analyzed_data[j]
                    try:
                        analyzed = AnalyzedListingDocument(
                            original_listing_id=listing.original_id,
                            brand=analysis.get("brand"),
                            model=analysis.get("model"),
                            variant=analysis.get("variant"),
                            info=analysis.get("info", {}),
                            analysis_version="1.0",
                        )
                        yield analyzed
                    except Exception as e:
                        self.logger.debug(f"Failed with analyzed data:\n{analyzed_data}")
                        self.logger.error(f"Error creating analyzed listing {j} in batch {batch_num}: {str(e)}")
                        continue
                progress_bar.update(1)

            except Exception as e:
                self.logger.error(f"Error during batch analysis: {str(e)}")
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

    async def _mark_failed(self, listing: ListingDocument, error: str):
        """Mark a listing as failed with error message."""
        listing.analysis_status = AnalysisStatus.FAILED
        listing.analysis_error = error
        listing.retry_count += 1
        await listing.save()

    async def bulk_create_analyses(self, analyses: List[AnalyzedListingDocument]):
        """Bulk create analyses."""
        [self.logger.debug(f"Creating {analysed}") for analysed in analyses]
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
