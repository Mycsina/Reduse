"""OLX scraper implementation."""

import asyncio
import json
import logging
import re
from decimal import Decimal
from typing import AsyncGenerator, List, Optional, cast

from bs4 import BeautifulSoup, Tag
from pydantic import HttpUrl
from tqdm.asyncio import tqdm as tqdm_asyncio

from ...config import settings
from ...schemas.listings import ListingDocument
from ...utils.playwright_pool import BrowserContext, get_pool
from .scraper_base import Scraper

BASE_URL = "https://www.olx.pt/"


class OLXScraper(Scraper):
    """Scraper for OLX Portugal website."""

    def __init__(self, max_concurrent_requests=None):
        """Initialize the OLX scraper."""
        self.base_url = BASE_URL
        self.logger = logging.getLogger(__name__)
        self._analyzed_ids = set()
        self.browser_pool = get_pool(max_concurrent_requests or settings.scraper.max_concurrent_requests)

    @classmethod
    def can_handle(cls, url: str) -> bool:
        """Check if this scraper can handle the given URL"""
        return url.startswith(BASE_URL) or url.startswith("https://www.olx.pt/")

    async def scrape_one(self, url: str) -> Optional[ListingDocument]:
        """Scrapes a single listing from its URL.

        Args:
            url: The URL of the individual listing (e.g., https://www.olx.pt/d/anuncio/...)
        """
        self.logger.info(f"Scraping individual listing: {url}")
        async with await self.browser_pool.acquire() as browser:
            try:
                src = await self._get_page_src(browser, url)
                if not src:
                    return None

                soup = BeautifulSoup(src, "html.parser")

                # Extract listing ID from JSON-LD script
                scripts = soup.find_all("script", {"type": "application/ld+json"})
                original_id = None
                for script in scripts:
                    try:
                        if script.string:
                            data = json.loads(script.string)
                            if data.get("@type") == "Product" and "sku" in data:
                                original_id = data["sku"]
                                break
                    except (json.JSONDecodeError, AttributeError) as e:
                        self.logger.debug(f"Failed to parse JSON-LD script: {str(e)}")
                        continue

                if not original_id:
                    self.logger.error("Could not find listing ID")
                    return None

                # Extract basic info
                title_elem = soup.find("div", {"data-cy": "ad_title"})
                if not title_elem.h4:  # type: ignore
                    self.logger.error("Could not find title element")
                    return None
                title = title_elem.h4.text.strip()  # type: ignore

                price_str = "Unavailable"
                price_value = None
                try:
                    price_elem = soup.find("h3", {"class": "css-12vqlj3"})
                    if price_elem:
                        price = price_elem.text.strip()
                        # First remove the euro symbol and any whitespace
                        price_str = price.strip().replace("€", "").strip()
                        # Remove any spaces that might be present
                        price_str = price_str.replace(" ", "")
                        # If there's only a dot and no comma, treat the dot as thousand separator
                        if price_str.count(".") == 1 and "," not in price_str:
                            price_str = price_str.replace(".", "")
                        # European format (1.234,56 or 1234,56)
                        elif "," in price_str:
                            # Remove dots (thousand separators)
                            price_str = price_str.replace(".", "")
                            # Replace comma with dot for decimal
                            price_str = price_str.replace(",", ".")
                        # Extract first number if there's a range
                        match = re.search(r"\d+\.?\d*", price_str)
                        if match:
                            price_str = match.group()
                            price_value = Decimal(price_str)
                        else:
                            price_str = "Unavailable"
                except Exception as e:
                    self.logger.debug(f"Failed to parse price: {e.__class__.__name__} - {str(e)}")

                # Create listing document
                return ListingDocument(
                    original_id=original_id,
                    site="olx",
                    title=title,
                    link=HttpUrl(url),
                    price_str=price_str,
                    price_value=price_value,
                    description=self.OLXParser._parse_description(src),
                    photo_urls=self.OLXParser._parse_photos(src),
                    more=False,
                )
            except Exception as e:
                self.logger.error(f"Error scraping individual listing: {str(e)}")
                return None

    async def scrape(self, url: str, already_scraped_ids: Optional[List[str]] = None) -> List[ListingDocument]:
        """Scrapes all listings from a URL and fetches their details.

        Args:
            url: The URL to scrape
            already_scraped_ids: Optional list of listing IDs that have already been scraped and should be ignored
        """
        try:
            self.logger.info(f"Starting scraping with details for URL: {url}")

            # If the URL is an individual listing, use scrape_one
            if "/d/anuncio/" in url:
                listing = await self.scrape_one(url)
                return [listing] if listing else []

            # Get all listings first
            listings = await self._fetch_all_listings(url)
            self.logger.info(f"Found {len(listings)} listings, fetching details in batches")

            # Filter out already scraped listings
            if already_scraped_ids:
                listings = [listing for listing in listings if listing.original_id not in already_scraped_ids]

            # Fetch details
            tasks = [self._fetch_listing_details(listing) for listing in listings if listing.site == "olx"]
            await tqdm_asyncio.gather(*tasks, desc="Fetching details: ")

            return listings
        except Exception as e:
            self.logger.error(f"Error during scraping with details: {str(e)}")
            return []

    async def _get_page_src(
        self,
        browser_context: BrowserContext,
        url: str,
        max_retries: int = 0,
        initial_retry_delay: float = 0.0,
    ) -> str:
        """Fetches the page source using Playwright with retries."""
        max_retries = max_retries or settings.scraper.retries["max_attempts"]
        initial_retry_delay = initial_retry_delay or settings.scraper.retries["initial_delay"]
        backoff_factor = settings.scraper.retries["backoff_factor"]

        async def _fetch():
            retry_delay = initial_retry_delay
            for attempt in range(max_retries):
                page = None
                try:
                    page = await browser_context.new_page()
                    self.logger.debug(f"Navigating to {url} (attempt {attempt + 1}/{max_retries})")

                    # Wait for either the navigation or a timeout
                    await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=settings.scraper.timeouts["page_load"],
                    )

                    # If browser hasn't accepted cookies, accept them
                    if not browser_context.__annotations__.get("cookies_accepted", False):
                        self.logger.debug("Looking for cookie consent button")
                        elem = await page.wait_for_selector(
                            "#onetrust-accept-btn-handler",
                            timeout=settings.scraper.timeouts["cookie_consent"],
                        )
                        if elem:
                            await elem.click()
                            browser_context.__annotations__["cookies_accepted"] = True
                            self.logger.debug("Accepted cookie consent")

                    src = await page.content()
                    await page.close()

                    if not src:
                        raise Exception("Received empty page source")

                    return src

                except Exception as e:
                    if page:
                        await page.close()
                    if attempt < max_retries - 1:
                        self.logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}. "
                            f"Retrying in {retry_delay} seconds..."
                        )
                        await asyncio.sleep(retry_delay)
                        retry_delay *= backoff_factor
                    else:
                        self.logger.error(f"All {max_retries} attempts to get page source from {url} failed: {str(e)}")
                        return ""

            return ""

        return await _fetch()

    async def scrape_all(self) -> AsyncGenerator[List[ListingDocument], None]:
        """Parses all categories from the homepage and returns their listings without details."""
        try:
            self.logger.info("Starting category parsing")

            # Get homepage content
            async with await self.browser_pool.acquire() as browser:
                src = await self._get_page_src(browser, self.base_url)
                if not src:
                    raise Exception("Failed to get homepage content")

                # Extract categories
                categories = self.OLXParser._parse_categories(src)
                self.logger.info(f"Found {len(categories)} categories to parse")

            # Parse each category with progress bar
            batch = []
            batch_size = settings.scraper.batch_size["listings"]

            # Create progress bar for categories
            async for category in tqdm_asyncio(categories, desc="Parsing categories"):
                if not isinstance(category, dict):
                    raise ValueError(f"This should never happen: {category} is not a dictionary")
                try:
                    self.logger.info(f"Parsing category: {category['name']}")
                    listings = await self._fetch_all_listings(category["url"])
                    if listings:
                        self.logger.info(f"Found {len(listings)} listings in category {category['name']}")
                        batch.extend(listings)

                        if len(batch) >= batch_size:
                            yield batch
                            batch = []

                except Exception as e:
                    self.logger.error(f"Error parsing category {category['name']}: {str(e)}")

            # Yield any remaining listings
            if batch:
                yield batch

            self.logger.info("Completed category parsing")

        except Exception as e:
            self.logger.error(f"Error during category parsing: {str(e)}")

    async def _fetch_listing_details(self, listing: ListingDocument) -> ListingDocument:
        """Fetch details for a single listing."""
        self.logger.debug(f"Fetching details for listing: {listing.title}")
        async with await self.browser_pool.acquire() as browser:
            try:
                listing_src = await self._get_page_src(browser, listing.link.unicode_string())
                listing.description = self.OLXParser._parse_description(listing_src)
                listing.photo_urls = self.OLXParser._parse_photos(listing_src)
                listing.more = False  # We've fetched all details
                self.logger.info(f"Got details for listing: {listing.title}")
                return listing
            except Exception as e:
                self.logger.error(f"Error fetching details for listing {listing.title}: {str(e)}")
                raise

    async def _fetch_page_listings(self, url: str, page: int) -> List[ListingDocument]:
        """Fetches all listings from a single result page."""
        self.logger.debug(f"Start _fetch_page_listings for {url} page {page}")
        async with await self.browser_pool.acquire() as browser:
            page_url = f"{url}?page={page}"
            src = await self._get_page_src(browser, page_url)
            return self.OLXParser._parse_listing_cards(src, self._analyzed_ids)

    async def _fetch_all_listings(self, url: str) -> List[ListingDocument]:
        """Fetches all listings from all result pages."""
        try:
            async with await self.browser_pool.acquire() as browser:
                # Get first page and page count together
                src = await self._get_page_src(browser, url)
                page_count = self.OLXParser._parse_page_count(src)
                first_page_listings = self.OLXParser._parse_listing_cards(src, self._analyzed_ids)
                self.logger.info(f"Found {len(first_page_listings)} listings on first page")

                # Create tasks for remaining pages
                remaining_tasks = [self._fetch_page_listings(url, page) for page in range(2, page_count + 1)]

                if remaining_tasks:
                    # Create progress bar for remaining page fetching
                    desc = f"Fetching {len(remaining_tasks)} remaining pages"
                    self.logger.info(f"Start fetching remaining pages for {url}")

                    # Use tqdm_asyncio.gather with the tasks list
                    remaining_listings = await tqdm_asyncio.gather(*remaining_tasks, desc=desc)

                    # Combine first page with remaining pages
                    all_listings = [first_page_listings] + remaining_listings
                else:
                    all_listings = [first_page_listings]

                # Flatten the list of lists into a single list and filter out empty sublists
                return [listing for sublist in all_listings if sublist for listing in sublist]
        except Exception as e:
            self.logger.error(f"Error getting all listings: {str(e)}")
            return []
        finally:
            self.logger.debug("Finished _get_all_listings_in_results")

    class OLXParser:
        logger = logging.getLogger(__name__)

        @classmethod
        def _parse_description(cls, src: str) -> str:
            """Extracts the description from a listing page."""
            try:
                soup = BeautifulSoup(src, "html.parser")
                description_div = soup.find("div", {"data-testid": "ad_description"})
                if description_div and isinstance(description_div, Tag):
                    div_content = description_div.find("div")
                    if div_content and isinstance(div_content, Tag):
                        return div_content.text
                return "Description not found"
            except Exception as e:
                cls.logger.error(f"Error getting description: {str(e)}")
                return "Error getting description"

        @classmethod
        def _parse_photos(cls, src: str) -> List[HttpUrl]:
            """Extracts photo URLs from a listing page."""
            try:
                soup = BeautifulSoup(src, "html.parser")
                photo_parents = soup.find_all("div", {"data-testid": "ad-photo"})
                return [HttpUrl(photo_parent.div.img["src"]) for photo_parent in photo_parents]
            except Exception as e:
                cls.logger.error(f"Error getting photos: {str(e)}")
                return []

        @classmethod
        def _parse_listing_cards(cls, src: str, analyzed_ids: set) -> List[ListingDocument]:
            """Parses listing cards from HTML source without fetching details."""
            listings = []

            try:
                soup = BeautifulSoup(src, "html.parser")
                listing_cards = soup.find_all("div", {"data-cy": re.compile("l-card")})

                for card in listing_cards:
                    try:
                        original_id = card["id"]
                        link = card.find("a")["href"]

                        # Determine if it's an external listing
                        is_external = not (link.startswith("/") or link.startswith(BASE_URL))
                        site = OLXScraper._get_site_from_url(link) if is_external else "olx"

                        # Normalize internal links
                        if not is_external and link.startswith("/"):
                            link = BASE_URL + link

                        title = card.find("div", {"data-cy": "ad-card-title"}).a.h4.text
                        try:
                            price = card.find("p", {"data-testid": "ad-price"}).text
                            # First remove the euro symbol and any whitespace
                            price_str = price.strip().replace("€", "").strip()

                            # Remove any spaces that might be present
                            price_str = price_str.replace(" ", "")

                            # If there's only a dot and no comma, treat the dot as thousand separator
                            if price_str.count(".") == 1 and "," not in price_str:
                                price_str = price_str.replace(".", "")
                            # European format (1.234,56 or 1234,56)
                            elif "," in price_str:
                                # Remove dots (thousand separators)
                                price_str = price_str.replace(".", "")
                                # Replace comma with dot for decimal
                                price_str = price_str.replace(",", ".")

                            # Extract first number if there's a range
                            match = re.search(r"\d+\.?\d*", price_str)
                            price_str = match.group() if match else None
                            price_value = Decimal(price_str) if price_str else None
                            cls.logger.debug(f"Parsed price '{price}' -> '{price_str}' -> {price_value}")
                        except Exception as e:
                            cls.logger.debug(f"Failed to parse price: {e.__class__.__name__} - {str(e)}")
                            price_value = None
                        if not price_str:
                            price_str = "Unavailable"

                        # Filter out already analyzed listings
                        if original_id not in analyzed_ids:
                            listings.append(
                                ListingDocument(
                                    original_id=original_id,
                                    site=site,
                                    title=title,
                                    link=link,
                                    price_str=price_str,
                                    price_value=price_value,
                                    description=None,
                                    more=True,  # All listings from category view have more details to fetch
                                )
                            )
                    except Exception as e:
                        cls.logger.error(f"Error parsing individual card: {str(e)}")
                        continue

                internal_count = sum(1 for listing in listings if listing.site == "olx")
                external_count = len(listings) - internal_count
                cls.logger.debug(f"Parsed {len(listings)} listings ({internal_count} OLX, {external_count} external)")
                return listings
            except Exception as e:
                cls.logger.error(f"Error parsing listing cards: {str(e)}")
                return []

        @classmethod
        def _parse_page_count(cls, src: str) -> int:
            """Extracts the total number of result pages from page source."""
            try:
                soup = BeautifulSoup(src, "html.parser")
                if not isinstance(soup, BeautifulSoup):
                    cls.logger.error("Failed to create BeautifulSoup object")
                    return 1

                # Cast soup to BeautifulSoup to ensure type safety
                soup = cast(BeautifulSoup, soup)
                pagination = soup.find_all("li", {"data-testid": "pagination-list-item"})
                if not pagination:
                    cls.logger.info("No pagination found, assuming single page")
                    return 1

                last_page_element = pagination[-1]
                if not last_page_element.a:
                    cls.logger.warning("Last page element has no link, defaulting to 1")
                    return 1

                page_count = int(last_page_element.a.text)
                cls.logger.info(f"Found {page_count} pages to scrape")
                return page_count
            except (AttributeError, IndexError, ValueError) as e:
                cls.logger.warning(f"Could not get page count, defaulting to 1: {str(e)}")
                return 1
            except Exception as e:
                cls.logger.error(f"Unexpected error getting page count: {str(e)}")
                return 1

        @classmethod
        def _parse_categories(cls, src: str) -> List[dict]:
            """Extracts category links from the homepage."""
            try:
                soup = BeautifulSoup(src, "html.parser")
                categories_menu = soup.find("div", {"data-testid": "home-categories-menu"})
                if not categories_menu:
                    return []

                categories = []
                for link in categories_menu.find_all("a", {"class": ["css-1ep67ka", "css-60fzsg"]}):  # type: ignore
                    # Skip promotional categories
                    if "cat-promo" in link.get("data-testid", ""):
                        continue

                    href = link.get("href")
                    if href and not href.startswith("http"):
                        href = BASE_URL + href.lstrip("/")

                    name = link.find("p")
                    categories.append(
                        {
                            "name": name.text if name else "Unknown",
                            "url": href,
                            "id": link.get("data-check", "unknown"),
                        }
                    )

                return categories
            except Exception as e:
                cls.logger.error(f"Error extracting categories: {str(e)}")
                return []
