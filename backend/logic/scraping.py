import logging
from typing import Dict, List, Tuple

from crawlee.configuration import Configuration
from crawlee.storages import Dataset

from backend.logic.analysis import analyze_batch, bulk_create_analyses
from backend.schemas.listings import AnalysisStatus, ListingDocument
from backend.services.crawler.crawler import Crawler
from backend.services.crawler.router import RouterWrapper
from backend.services.listings import save_listings

logger = logging.getLogger(__name__)


async def scrape_and_save(url: str) -> List[ListingDocument]:
    """Scrapes a URL with details using the Crawler and saves the data to the database."""
    logger.info(f"Starting CRAWLER scraping for URL: {url}")
    saved_listings = []
    try:
        # Instantiate the router and crawler
        router_wrapper = RouterWrapper()
        crawler_router = router_wrapper.get_router()
        crawler_instance = Crawler(router=crawler_router)
        playwright_crawler = await crawler_instance.get_crawler()

        # TODO: keep state from previous incomplete crawls, need to study if it should be toggleable
        dataset = await Dataset.open(configuration=Configuration(purge_on_start=False))

        logger.info("Running crawler...")
        await playwright_crawler.run([url], purge_request_queue=False)
        logger.info(f"Crawler run finished for URL: {url}.")

        # Retrieve and save data iteratively, prioritizing detailed listings
        logger.debug(f"Processing and saving data from dataset...")
        processed_listings: Dict[Tuple[str, str], ListingDocument] = {}
        async for item in dataset.iterate_items():
            try:
                current_listing = ListingDocument(**item)
                oid = current_listing.original_id
                site = current_listing.site
                logger.debug(
                    f"Processing item from dataset: original_id={oid}, site={site}, more={current_listing.more}"
                )
                if not oid or not site:
                    logger.warning(f"Skipping item without original_id or site: {item}")
                    continue

                composite_key = (oid, site)
                existing_listing = processed_listings.get(composite_key)

                # Keep the current listing if it's the first one found for this key,
                # or if the current one is detailed (more=False) and the existing one is not.
                if not existing_listing or (
                    existing_listing.more and not current_listing.more
                ):
                    processed_listings[composite_key] = current_listing
                    logger.debug(
                        f"Adding/Updating processed_listings for key={composite_key} (more={current_listing.more})"
                    )

            except Exception as e:
                logger.warning(
                    f"Failed to parse item into ListingDocument or process: {item}. Error: {e}",
                    exc_info=True,
                )

        listings_to_save = list(processed_listings.values())
        logger.info(
            f"Processed {len(listings_to_save)} unique/detailed items from dataset."
        )

        if listings_to_save:
            logger.debug(
                f"Attempting to save {len(listings_to_save)} listings to database..."
            )
            await save_listings(listings_to_save)

            # Refetch saved listings to get database IDs needed for analysis step
            original_ids = [l.original_id for l in listings_to_save]
            saved_listings = await ListingDocument.find_many(
                {"original_id": {"$in": original_ids}}
            ).to_list()
            logger.info(f"Successfully saved {len(saved_listings)} listings.")

        return saved_listings

    except Exception as e:
        logger.error(
            f"An error occurred during crawling for URL: {url}. Error: {e}",
            exc_info=True,
        )
        return []


async def scrape_analyze_and_save(url: str):
    """Scrapes a URL, saves the listings, analyzes them, and saves the analysis."""
    logger.info(f"Starting scrape, analyze, and save process for URL: {url}")

    # Step 1: Scrape and Save
    scraped_listings = await scrape_and_save(url)

    if not scraped_listings:
        logger.warning(f"No listings were saved for URL: {url}. Skipping analysis.")
        return

    logger.info(
        f"Successfully scraped and saved {len(scraped_listings)} listings. Starting analysis..."
    )

    # Step 2: Analyze
    analysis_results = []
    successful_listing_ids = (
        set()
    )  # Use a set to store IDs of successfully analyzed listings
    try:
        # Use analyze_batch for efficiency
        async for original, analyzed in analyze_batch(scraped_listings, batch_size=10):
            if analyzed:
                analysis_results.append(analyzed)
                successful_listing_ids.add(
                    original.id
                )  # Store the Mongo _id from the original object
            else:
                # Handle analysis failure for individual item if needed
                logger.warning(f"Analysis failed for listing: {original.original_id}")
                # Listing status is already marked as FAILED inside analyze_batch

        logger.info(
            f"Analysis completed. {len(analysis_results)} listings successfully analyzed."
        )

        # Step 3: Save Analysis Results
        if analysis_results:
            logger.info(f"Saving {len(analysis_results)} analysis results...")
            await bulk_create_analyses(analysis_results)
            logger.info("Successfully saved analysis results.")

            # Step 4: Update Listing Status (only for successfully analyzed ones)
            if successful_listing_ids:
                logger.info(
                    f"Updating status to COMPLETED for {len(successful_listing_ids)} listings..."
                )
                await ListingDocument.find_many(
                    {"_id": {"$in": list(successful_listing_ids)}}
                ).update_many({"$set": {"analysis_status": AnalysisStatus.COMPLETED}})
                logger.info(
                    f"Successfully updated status for {len(successful_listing_ids)} listings."
                )
            # No need for else/fallback, status is updated based on the _id collected

        else:
            logger.info("No analysis results to save.")

    except Exception as e:
        logger.error(
            f"An error occurred during analysis batch processing or saving analysis for URL: {url}. Error: {e}",
            exc_info=True,
        )
        # Mark *all* initially scraped listings as FAILED if the whole batch process fails
        # Note: Listings that failed *within* the batch were already marked FAILED.
        # This marks listings that might not have even started analysis due to the broader error.
        initial_ids = [l.id for l in scraped_listings]
        await ListingDocument.find_many(
            {
                "_id": {"$in": initial_ids},
                "analysis_status": {"$ne": AnalysisStatus.COMPLETED},
            }
        ).update_many(
            {
                "$set": {
                    "analysis_status": AnalysisStatus.FAILED,
                    "analysis_error": f"Batch processing error: {e}",
                }
            }
        )

    logger.info(f"Scrape, analyze, and save process finished for URL: {url}")
