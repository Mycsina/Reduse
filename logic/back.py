import logging
from typing import List

from ..schemas.listings import ListingDocument
from ..services.olx import OLXScraper
from ..services.scraper_base import ScraperRegistry
from .analysis import analyze_new_listings

scraper_registry = ScraperRegistry()


async def scrape_and_save(url: str, rate_limit: bool = True):
    """Scrapes a URL and save listings."""
    logging.info(f"Starting scraping for URL: {url}")
    try:
        scraper_class = scraper_registry.get_scraper(url)
        scraper = scraper_class()

        if isinstance(scraper, OLXScraper):
            listings = await scraper.scrape(url)

        logging.info(f"Found {len(listings)} listings for URL: {url}")

        await save_listings(listings)

        logging.info(f"Finished scraping and saving for URL: {url}. Saved {len(listings)} new listings.")

    except ValueError as e:
        logging.error(f"No scraper found for URL: {url}. Error: {e}")
    except Exception as e:
        logging.error(f"An error occurred during scraping or saving for URL: {url}. Error: {e}")


async def scrape_analyze_and_save(url: str, rate_limit: bool = True):
    """Scrapes a URL with details, saves listings, and analyzes them."""
    logging.info(f"Starting scraping with details for URL: {url}")
    try:
        scraper_class = scraper_registry.get_scraper(url)
        scraper = scraper_class()

        listings = await scraper.scrape(url)

        logging.info(f"Found {len(listings)} listings for URL: {url}")

        await save_listings(listings)

        logging.info(f"Finished scraping and saving for URL: {url}. Saved {len(listings)} new listings.")

        # Analyze new listings
        await analyze_new_listings()

    except ValueError as e:
        logging.error(f"No scraper found for URL: {url}. Error: {e}")
    except Exception as e:
        logging.error(f"An error occurred during scraping or saving for URL: {url}. Error: {e}")


async def parse_olx_categories(rate_limit: bool = True):
    """Parse all OLX categories and save listings without details."""
    try:
        scraper = OLXScraper()

        total_saved = 0

        async for batch in scraper.scrape_all():
            await save_listings(batch)
            total_saved += len(batch)

        logging.info(f"Finished parsing and saving all categories. Total saved: {total_saved} listings")

    except Exception as e:
        logging.error(f"Error during OLX category parsing: {str(e)}")


async def save_listings(listings: List[ListingDocument]) -> None:
    """Save listings to the database."""
    await ListingDocument.insert_many(listings)
    logging.info(f"Saved {len(listings)} listings")
