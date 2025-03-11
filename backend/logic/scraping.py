import logging

from ..schemas.listings import ListingDocument, OriginalId, save_listings
from ..services.scraper import (OLXScraper, ScraperNotFoundError,
                                ScraperRegistry)
from .analysis import analyze_new_listings

scraper_registry = ScraperRegistry()


async def scrape_and_save(url: str, rate_limit: bool = True):
    """Scrapes a URL and save listings."""
    logging.info(f"Starting scraping for URL: {url}")
    try:
        scraper_class = scraper_registry.get_scraper(url)
        scraper = scraper_class()

        logging.info(f"Scraping {url} with {scraper_class.__name__}")

        listings = await scraper.scrape(url)

        logging.info(f"Found {len(listings)} listings for URL: {url}")

        await save_listings(listings)

        logging.info(
            f"Finished scraping and saving for URL: {url}. Saved {len(listings)} new listings."
        )

    except ScraperNotFoundError as e:
        logging.error(f"No scraper found for URL: {url}. Error: {e}")
    except Exception as e:
        logging.error(
            f"An error occurred during scraping or saving for URL: {url}. Error: {e}"
        )


async def scrape_analyze_and_save(url: str):
    """Scrapes a URL with details, saves listings, and analyzes them."""
    logging.info(f"Starting scraping with details for URL: {url}")
    try:
        scraper_class = scraper_registry.get_scraper(url)
        scraper = scraper_class()

        # Get already scraped listings
        already_scraped_ids = await ListingDocument.find().project(OriginalId).to_list()
        already_scraped_ids = [id.original_id for id in already_scraped_ids]

        listings = await scraper.scrape(url, already_scraped_ids)

        if not listings:
            logging.info(f"No new listings found for URL: {url}")
            return

        logging.info(f"Found {len(listings)} listings for URL: {url}")

        if not listings:
            logging.info(f"No new listings found for URL: {url}")

        await save_listings(listings)

        logging.info(
            f"Finished scraping and saving for URL: {url}. Saved {len(listings)} new listings."
        )

        # Analyze new listings
        await analyze_new_listings()

    except ScraperNotFoundError as e:
        logging.error(f"No scraper found for URL: {url}. Error: {e}")
    except Exception as e:
        logging.error(
            f"An error occurred during scraping or saving for URL: {url}. Error: {e}"
        )


async def scrape_olx_categories():
    """Parse all OLX categories and save listings without details."""
    try:
        scraper = OLXScraper()

        total_saved = 0

        async for batch in scraper.scrape_all():
            await save_listings(batch)
            total_saved += len(batch)

        logging.info(
            f"Finished parsing and saving all categories. Total saved: {total_saved} listings"
        )

    except Exception as e:
        logging.error(f"Error during OLX category parsing: {str(e)}")
