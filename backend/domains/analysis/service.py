"""Analysis service implementation."""

import logging
from typing import AsyncGenerator, Dict, List, Optional, Tuple, Union

from ...ai.prompts.product_analysis import create_product_analysis_prompt
from ...ai.providers.factory import AIProviderFactory
from ...models.analysis import AnalyzedListingDocument
from ...models.listings import ListingDocument
from ...schemas.analysis import AnalysisStatus
from ...utils.cache import cache
from ...utils.errors import AIProviderError

logger = logging.getLogger(__name__)


class AnalysisService:
    """Service for product listing analysis."""

    def __init__(self):
        """Initialize the analysis service."""
        self.logger = logging.getLogger(__name__)
        self.ai_provider = AIProviderFactory.create_provider()

    async def _generate_listing_embeddings(self, info: Dict, listing: ListingDocument) -> List[float]:
        """Generate embeddings for a listing based on its info.

        Args:
            info: Product information dictionary
            listing: Original listing document

        Returns:
            List of embedding values
        """
        # Create text for embedding generation
        embedding_text = f"{listing.title} {listing.description} "

        # Add structured info
        for key, value in info.items():
            if isinstance(value, list):
                value_str = ", ".join(value)
            else:
                value_str = str(value)
            embedding_text += f"{key}: {value_str} "

        # Generate and cache embeddings
        cache_key = f"embedding:{listing.id}"
        cached_embeddings = await cache.get_complex(cache_key)

        if cached_embeddings:
            self.logger.debug(f"Using cached embeddings for listing {listing.id}")
            return cached_embeddings

        try:
            embeddings = await self.ai_provider.get_embeddings(embedding_text)
            if embeddings and len(embeddings) > 0:
                # Cache embeddings with 1 week TTL
                await cache.set_complex(cache_key, embeddings[0], 86400 * 7)
                return embeddings[0]
            else:
                self.logger.warning(f"Empty embeddings for listing {listing.id}")
                return []
        except Exception as e:
            self.logger.error(f"Failed to generate embeddings: {e}")
            raise AIProviderError(f"Embedding generation failed: {str(e)}")

    async def _mark_status(self, listing: ListingDocument, status: AnalysisStatus) -> None:
        """Update listing analysis status.

        Args:
            listing: The listing document to update
            status: The new analysis status
        """
        listing.analysis_status = status
        await listing.save()
        self.logger.debug(f"Updated listing {listing.id} status to {status}")

    async def analyze_listing(self, listing: ListingDocument) -> Tuple[ListingDocument, AnalyzedListingDocument]:
        """Analyze a single product listing.

        Args:
            listing: The listing document to analyze

        Returns:
            Tuple of original listing and analyzed listing document

        Raises:
            AIProviderError: If analysis fails
        """
        self.logger.info(f"Analyzing listing {listing.id}")

        # Check cache first
        cache_key = f"analysis:{listing.id}"
        cached_analysis = await cache.get_object(cache_key, AnalyzedListingDocument)

        if cached_analysis:
            self.logger.debug(f"Using cached analysis for listing {listing.id}")
            return listing, cached_analysis

        # Mark as processing
        await self._mark_status(listing, AnalysisStatus.PROCESSING)

        try:
            # Create prompt for this listing
            prompt = create_product_analysis_prompt()
            input_text = f"Title: {listing.title or ''}\nDescription: {listing.description or ''}"

            # Make AI call for analysis
            self.logger.debug(f"Querying AI for listing {listing.original_id}")
            analysis = await self.ai_provider.generate_json(
                prompt=prompt.format(input=input_text),
                model=prompt.config.model_name,
                temperature=prompt.config.temperature,
                max_tokens=prompt.config.max_tokens,
            )

            # Process info fields
            info = analysis.get("info", {})

            # If field is a comma separated string, split it into a list
            for key, value in info.items():
                if isinstance(value, str) and "," in value:
                    info[key] = [item.strip() for item in value.split(",")]

            # Generate embeddings from the info struct
            embeddings = await self._generate_listing_embeddings(info, listing)

            # Create analyzed document
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

            # Save to database
            await analyzed.save()
            await self._mark_status(listing, AnalysisStatus.COMPLETED)

            # Cache the analysis
            await cache.set_object(cache_key, analyzed, 86400)  # 1 day TTL

            self.logger.info(f"Analysis completed for listing {listing.id}")
            return listing, analyzed

        except Exception as e:
            self.logger.error(f"Analysis failed for listing {listing.id}: {e}")
            await self._mark_status(listing, AnalysisStatus.FAILED)
            raise AIProviderError(f"Analysis failed: {str(e)}")

    async def analyze_batch(
        self, listings: List[ListingDocument], batch_size: int = 5
    ) -> AsyncGenerator[Tuple[ListingDocument, AnalyzedListingDocument], None]:
        """Analyze listings in batches, yielding results as they're processed.

        Args:
            listings: List of listings to analyze
            batch_size: Number of listings to process in parallel

        Yields:
            Tuples of original listing and analyzed listing document
        """
        self.logger.info(f"Starting batch analysis of {len(listings)} listings")

        # Process in batches to avoid overwhelming the AI provider
        for i in range(0, len(listings), batch_size):
            batch = listings[i : i + batch_size]
            self.logger.debug(f"Processing batch {i // batch_size + 1} of {len(listings) // batch_size + 1}")

            # Process each listing in the batch
            for listing in batch:
                try:
                    listing, analyzed = await self.analyze_listing(listing)
                    yield listing, analyzed
                except Exception as e:
                    self.logger.error(f"Batch analysis failed for listing {listing.id}: {e}")
                    # Continue with next listing instead of failing the whole batch
                    continue
