"""Repository for analysis domain."""

import logging
from typing import List, Optional, Tuple, Dict, Any

from ...models.analysis import AnalyzedListingDocument
from ...models.listings import ListingDocument
from ...schemas.analysis import AnalysisStatus, SearchFilter
from ...utils.errors import DocumentNotFoundError

logger = logging.getLogger(__name__)


class AnalysisRepository:
    """Repository for analysis data access."""

    def __init__(self):
        """Initialize the repository."""
        self.logger = logging.getLogger(__name__)

    async def get_analyzed_listing(self, listing_id: str) -> Optional[AnalyzedListingDocument]:
        """Get analyzed listing by original listing ID.

        Args:
            listing_id: Original listing ID

        Returns:
            Analyzed listing document or None if not found
        """
        return await AnalyzedListingDocument.find_one({"original_listing_id": listing_id})

    async def get_listings_for_analysis(
        self, limit: int = 50, skip: int = 0, status: Optional[AnalysisStatus] = None
    ) -> List[ListingDocument]:
        """Get listings ready for analysis.

        Args:
            limit: Maximum number of listings to return
            skip: Number of listings to skip
            status: Filter by analysis status

        Returns:
            List of listing documents
        """
        # Build query based on parameters
        query = {}
        if status:
            query["analysis_status"] = status
        else:
            # Default to getting listings that aren't completed or failed
            query["analysis_status"] = {"$nin": [AnalysisStatus.COMPLETED, AnalysisStatus.FAILED]}

        # Get listings sorted by creation date
        return await ListingDocument.find(query).sort([("created_at", -1)]).limit(limit).skip(skip).to_list()

    async def get_similar_listings(
        self, embeddings: List[float], limit: int = 10, exclude_ids: Optional[List[str]] = None
    ) -> List[AnalyzedListingDocument]:
        """Find similar listings using vector similarity.

        Args:
            embeddings: Vector embeddings to search against
            limit: Maximum number of results
            exclude_ids: Listing IDs to exclude from results

        Returns:
            List of similar listings
        """
        # Build pipeline for vector search
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "embeddings_index",
                    "path": "embeddings",
                    "queryVector": embeddings,
                    "numCandidates": limit * 4,  # Search more candidates for better results
                    "limit": limit if not exclude_ids else limit + len(exclude_ids),
                }
            },
            {"$project": {"_id": 1, "score": {"$meta": "vectorSearchScore"}, "embeddings": 0}},
        ]

        # Add stage to filter out excluded IDs if provided
        if exclude_ids:
            pipeline.append({"$match": {"_id": {"$nin": exclude_ids}}})

        # Add limit stage
        pipeline.append({"$limit": limit})

        # Execute aggregation
        results = await AnalyzedListingDocument.aggregate(pipeline).to_list()

        # Get full documents for the results
        if not results:
            return []

        result_ids = [result["_id"] for result in results]
        return await AnalyzedListingDocument.find({"_id": {"$in": result_ids}}).to_list()

    async def search_listings(
        self, filter_params: SearchFilter, limit: int = 50, skip: int = 0
    ) -> Tuple[List[AnalyzedListingDocument], int]:
        """Search for listings with filtering.

        Args:
            filter_params: Filter parameters
            limit: Maximum number of results
            skip: Number of results to skip

        Returns:
            Tuple of (results, total_count)
        """
        # Build query based on filter params
        query: Dict[str, Any] = {}

        if filter_params.brand:
            query["brand"] = {"$regex": filter_params.brand, "$options": "i"}

        if filter_params.type:
            query["type"] = {"$regex": filter_params.type, "$options": "i"}

        if filter_params.base_model:
            query["base_model"] = {"$regex": filter_params.base_model, "$options": "i"}

        if filter_params.model_variant:
            query["model_variant"] = {"$regex": filter_params.model_variant, "$options": "i"}

        # Additional info filters
        if filter_params.info_fields:
            for key, value in filter_params.info_fields.items():
                query[f"info.{key}"] = {"$regex": value, "$options": "i"}

        # Execute query
        results = await AnalyzedListingDocument.find(query).sort([("created_at", -1)]).limit(limit).skip(skip).to_list()

        # Count total matches
        total = await AnalyzedListingDocument.find(query).count()

        return results, total

    async def update_analysis_status(self, listing_id: str, status: AnalysisStatus) -> ListingDocument:
        """Update the analysis status of a listing.

        Args:
            listing_id: Listing ID
            status: New analysis status

        Returns:
            Updated listing document

        Raises:
            DocumentNotFoundError: If the listing is not found
        """
        listing = await ListingDocument.find_one({"_id": listing_id})
        if not listing:
            raise DocumentNotFoundError("Listing", {"_id": listing_id})

        listing.analysis_status = status
        return await listing.save()
