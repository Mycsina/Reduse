import asyncio
import logging
import random
import re
from decimal import Decimal
from typing import AsyncGenerator, List, cast

from bs4 import BeautifulSoup, Tag
from tqdm.asyncio import tqdm as tqdm_asyncio

from ..config import SCRAPER_CONFIG
from ..schemas.listings import ListingDocument
from ..utils.playwright_pool import BrowserContext, get_pool
from .scraper_base import Scraper as BaseScraper

BASE_URL = "https://www.olx.pt/"


class OLXScraper(BaseScraper):
    """Scraper for OLX Portugal website.

    This scraper handles both OLX listings and external listings that appear on OLX.
    It supports concurrent scraping with a pool of browser instances and implements
    various scraping strategies with retries and error handling.

    Attributes:
        base_url: Base URL for OLX Portugal
        logger: Logger instance for scraper-specific logging
        _analyzed_ids: Set of already analyzed listing IDs
        browser_pool: PlaywrightPool instance for managing browser sessions
    """

    def __init__(self, max_concurrent_requests=None):
        """Initialize the OLX scraper."""
        self.base_url = BASE_URL
        self.logger = logging.getLogger(__name__)
        self._analyzed_ids = set()
        self.browser_pool = get_pool(max_concurrent_requests or SCRAPER_CONFIG["max_concurrent_requests"])

    async def scrape(self, url: str) -> List[ListingDocument]:
        """Scrapes all listings from a URL and fetches their details."""
        try:
            self.logger.info(f"Starting scraping with details for URL: {url}")

            # Get all listings first
            listings = await self._fetch_all_listings(url)
            self.logger.info(f"Found {len(listings)} listings, fetching details in batches")

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
        scroll_to_bottom: bool = False,
        max_retries: int = SCRAPER_CONFIG["retries"]["max_attempts"],
        initial_retry_delay: float = SCRAPER_CONFIG["retries"]["initial_delay"],
    ) -> str:
        """Fetches the page source using Playwright with retries."""
        backoff_factor = SCRAPER_CONFIG["retries"]["backoff_factor"]
        logging.debug(
            f"Max retries: {max_retries}, initial retry delay: {initial_retry_delay}, backoff factor: {backoff_factor}"
        )

        async def _scroll_down_gradually(page, scroll_step=1000, scroll_delay_min=10, scroll_delay_max=300):
            """Scrolls a page down gradually to simulate human-like scrolling."""
            last_height = await page.evaluate("document.documentElement.scrollTop")
            total_scrolled = 0

            while True:
                scroll_amount = random.randint(scroll_step // 2, scroll_step)
                await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                total_scrolled += scroll_amount

                await asyncio.sleep(random.randint(scroll_delay_min, scroll_delay_max) / 1000.0)

                new_height = await page.evaluate("document.documentElement.scrollTop")
                if new_height == last_height:
                    break
                last_height = new_height
                self.logger.debug(f"Scrolled {total_scrolled}px of {new_height}px")

        async def _fetch():
            retry_delay = initial_retry_delay
            for attempt in range(max_retries):
                page = None
                try:
                    page = await browser_context.new_page()
                    self.logger.debug(f"Navigating to {url} (attempt {attempt + 1}/{max_retries})")

                    # Wait for either the navigation or a timeout
                    await page.goto(url, wait_until="domcontentloaded", timeout=SCRAPER_CONFIG["timeouts"]["page_load"])

                    # If browser hasn't accepted cookies, accept them
                    if not browser_context.__annotations__.get("cookies_accepted", False):
                        self.logger.debug("Looking for cookie consent button")
                        elem = await page.wait_for_selector(
                            "#onetrust-accept-btn-handler", timeout=SCRAPER_CONFIG["timeouts"]["cookie_consent"]
                        )
                        if elem:
                            await elem.click()
                            browser_context.__annotations__["cookies_accepted"] = True
                            self.logger.debug("Accepted cookie consent")

                    if scroll_to_bottom:
                        self.logger.info("Starting gradual scroll to bottom")
                        await _scroll_down_gradually(page)
                        self.logger.info("Completed scrolling to bottom")

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
            batch_size = SCRAPER_CONFIG["batch_size"]["listings"]

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
                listing.location = self.OLXParser._parse_location(listing_src)
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
            src = await self._get_page_src(browser, page_url, scroll_to_bottom=True)
            return self.OLXParser._parse_listing_cards(src, self._analyzed_ids)

    async def _fetch_all_listings(self, url: str) -> List[ListingDocument]:
        """Fetches all listings from all result pages."""
        try:
            async with await self.browser_pool.acquire() as browser:
                # Get first page and page count together
                src = await self._get_page_src(browser, url, scroll_to_bottom=True)
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
        def _parse_location(cls, src: str) -> str:
            """Extracts the location from a listing page."""
            try:
                soup = BeautifulSoup(src, "html.parser")
                location_div = soup.find("div", {"class": "css-13l8eec"})
                if location_div and isinstance(location_div, Tag):
                    div_content = location_div.find("div")
                    if div_content and isinstance(div_content, Tag):
                        return div_content.text
                return "Location not found"
            except Exception as e:
                cls.logger.error(f"Error getting location: {str(e)}")
                return "Error getting location"

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
                        site = cls.__bases__[-1]._get_site_from_url(link) if is_external else "olx"

                        # Normalize internal links
                        if not is_external and link.startswith("/"):
                            link = BASE_URL + link

                        title = card.find("div", {"data-cy": "ad-card-title"}).a.h4.text
                        try:
                            price = card.find("p", {"data-testid": "ad-price"}).text
                            price_str = price.replace("€", "").replace(",", ".").split(" ")[0]
                            price_value = Decimal(price_str) if price_str else None
                        except (AttributeError, ValueError):
                            price = "Unavailable"
                            price_value = None
                        photo_url = card.find("img")["src"]
                        # Clean photo URL by removing size and quality parameters
                        if photo_url:
                            photo_url = photo_url.split(";")[0]

                        # Filter out already analyzed listings
                        if original_id not in analyzed_ids:
                            listings.append(
                                ListingDocument(
                                    original_id=original_id,
                                    site=site,
                                    title=title,
                                    link=link,
                                    price_str=price,
                                    price_value=price_value,
                                    photo_url=photo_url,
                                    description=None,
                                    location=None,
                                    more=True,  # All listings from category view have more details to fetch
                                )
                            )
                    except Exception as e:
                        cls.logger.error(f"Error parsing individual card: {str(e)}")
                        continue

                internal_count = sum(1 for listing in listings if listing.site == "olx")
                external_count = len(listings) - internal_count
                cls.logger.info(f"Parsed {len(listings)} listings ({internal_count} OLX, {external_count} external)")
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
                        {"name": name.text if name else "Unknown", "url": href, "id": link.get("data-check", "unknown")}
                    )

                return categories
            except Exception as e:
                cls.logger.error(f"Error extracting categories: {str(e)}")
                return []
