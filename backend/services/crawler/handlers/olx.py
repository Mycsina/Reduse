import asyncio
import json
import logging
import re
from enum import Enum
from typing import List
from urllib.parse import urlparse

from crawlee import Request
from crawlee.crawlers import PlaywrightCrawlingContext
from playwright.async_api import Page
from pydantic import HttpUrl

from backend.schemas.listings import ListingDocument
from backend.services.crawler.handlers.handlers import WebsiteHandler, label
from backend.services.crawler.integration import get_already_crawled, simple_hash

logger = logging.getLogger(__name__)

BASE_URL = "https://www.olx.pt"
SITE = "olx"
BASE_HANDLER = WebsiteHandler.OLX


class OLXLabels(Enum):
    HOMEPAGE = "homepage"
    LISTINGS = "listings"
    DETAIL = "detail"


def _get_site_from_url(url: str) -> str:
    """Extract site name from URL."""
    if url.startswith(BASE_URL):
        return SITE
    try:
        domain = urlparse(url).netloc
        return domain.split(".")[-2]  # Return second-level domain
    except Exception:
        return "external"


def _parse_price(price_text: str) -> tuple[str, float | None]:
    """Parses the price string into a standard format and float value."""
    try:
        # Handle cases with extra text
        price_txt, _ = price_text.split("€", 1)
        price_str = price_txt.replace(" ", "").replace(".", "").replace(",", ".")
        price_value = float(price_str)
        return price_str, price_value
    except Exception as e:
        logger.debug(f"Failed to parse price '{price_text}': {e}")
        return "Unavailable", None


async def _parse_description(page: Page) -> str:
    """Extracts the description from a listing page using Playwright."""
    try:
        description_div = page.locator('[data-testid="ad_description"] div')
        if await description_div.count() > 0:
            return await description_div.inner_text()
        return "Description not found"
    except Exception as e:
        logger.error(f"Error getting description: {str(e)}")
        return "Error getting description"


async def _parse_photos(page: Page) -> List[HttpUrl]:
    """Extracts photo URLs from a listing page using Playwright."""
    urls = []
    try:
        photo_locators = page.locator('[data-testid="ad-photo"] img')
        for i in range(await photo_locators.count()):
            src = await photo_locators.nth(i).get_attribute("src")
            if src:
                try:
                    urls.append(HttpUrl(src))
                except Exception as e_url:
                    logger.warning(f"Invalid photo URL '{src}': {e_url}")
    except Exception as e:
        logger.error(f"Error getting photos: {str(e)}")
    return urls


async def _parse_page_count(page: Page) -> int:
    """Extracts the total number of result pages from page source using Playwright."""
    try:
        pagination_items = page.locator('[data-testid="pagination-list-item"]')
        count = await pagination_items.count()
        if count == 0:
            logger.info("No pagination found, assuming single page")
            return 1

        last_page_link = pagination_items.nth(count - 1).locator("a")
        if await last_page_link.count() == 0:
            # Sometimes the last item isn't a link if it's the current page
            last_page_text_loc = pagination_items.nth(count - 1)
            last_page_text = await last_page_text_loc.inner_text()
            if last_page_text.isdigit():
                page_count = int(last_page_text)
                logger.info(f"Found {page_count} pages (using text)")
                return page_count
            else:
                logger.warning("Last page element has no link or text, defaulting to 1")
                return 1

        page_count_text = await last_page_link.inner_text()
        page_count = int(page_count_text)
        logger.info(f"Found {page_count} pages to scrape")
        return page_count
    except (AttributeError, IndexError, ValueError) as e:
        logger.warning(f"Could not get page count, defaulting to 1: {str(e)}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error getting page count: {str(e)}")
        return 1


# --- Handler Functions ---


@label(BASE_HANDLER.value)  # type: ignore
async def handle_olx(context: PlaywrightCrawlingContext) -> None:
    """
    Base handler for all OLX pages. Determines the type of page and calls the appropriate handler.
    Base webpage with categories is https://www.olx.pt
    Listings have a base + (/ads/|/{category})/q-{query}/
    Details have a base + /d/anuncio/ + {title} + .html
    """
    url = context.request.url
    logger.info(f"Routing URL: {url}")

    # Check for base URL with or without trailing slash
    if url == BASE_URL or url == BASE_URL + "/":
        logger.debug(f"Calling homepage handler for {url}")
        await handle_olx_homepage(context)
    elif "/d/anuncio/" in url:
        logger.debug(f"Calling detail handler for {url}")
        await handle_olx_detail(context)
    elif "/q-" in url or "/ads/" in url or "/carros-motos-e-barcos/" in url:  # Basic check for listings
        logger.debug(f"Calling listings handler for {url}")
        await handle_olx_listings(context)
    else:
        logger.warning(f"No specific handler matched for OLX URL: {url}. Using default enqueueing.")
        pass


@label(OLXLabels.HOMEPAGE.value)  # type: ignore
async def handle_olx_homepage(context: PlaywrightCrawlingContext) -> None:
    """
    Handles the base OLX URL (homepage). Enqueues category links found in the main menu.
    """
    logger.info(f"Processing homepage: {context.request.url}")

    # Use enqueue_links to find and enqueue category links directly
    await context.enqueue_links(
        selector='div[data-testid="home-categories-menu-row"] a',  # Target the same links as before
        label=str(OLXLabels.LISTINGS.value),  # Label them as listing pages
        strategy="same-domain",  # Use fully qualified name
    )
    logger.info("Finished enqueueing category links from homepage.")


@label(OLXLabels.LISTINGS.value)  # type: ignore
async def handle_olx_listings(context: PlaywrightCrawlingContext) -> None:
    """
    Handles OLX listing pages (search results, categories).
    Parses listing cards, extracts basic info, enqueues detail pages, and handles pagination.
    """
    page = context.page
    current_url = context.request.url
    logger.info(f"Processing listings page: {current_url}")

    # Fetch parsed_ids inside the async function
    parsed_ids = (await get_already_crawled()).get(SITE, {})

    listing_cards = page.locator('div[data-cy^="l-card"]')
    count = await listing_cards.count()
    logger.info(f"Found {count} listing cards on page.")

    for i in range(count):
        card = listing_cards.nth(i)
        card_id = await card.get_attribute("id")

        if not card_id:
            logger.warning(f"Card {card_id} found without ID, skipping.")
            continue

        link_elem = card.locator("a").first
        price_element = card.locator('p[data-testid="ad-price"]')

        title_text = await link_elem.text_content()
        price_text = await price_element.text_content()

        if title_text is None or price_text is None:
            continue

        if not price_text:
            logger.warning("Price not found, skipping")
            continue

        price_str, price_value = _parse_price(price_text)

        href = await link_elem.get_attribute("href")
        if not href:
            logger.warning(f"Card {card_id} found without href, skipping.")
            continue

        # Determine if it's an external listing
        is_external = not (href.startswith("/") or href.startswith(BASE_URL))
        site = _get_site_from_url(href) if is_external else SITE

        # Normalize internal links
        if not is_external and href.startswith("/"):
            href = BASE_URL + href

        if card_id in parsed_ids:
            hash = simple_hash(title_text, price_str)
            if hash == parsed_ids[card_id].content_hash and not parsed_ids[card_id].more:
                logger.debug(f"Skipping fully crawled listing with unchanged content: {card_id}")
                continue

        if "/d/anuncio/" in href:
            logger.debug(f"Enqueueing detail page: {href}")
            await context.add_requests([Request.from_url(href, label=str(OLXLabels.DETAIL.value))])
        else:
            logger.debug(f"Found non-detail link, probably external: {href}")
            await context.add_requests([Request.from_url(href)])
            continue

        listing = ListingDocument(
            original_id=card_id,
            site=site,
            title=title_text,
            price_str=price_str,
            price_value=price_value,
            link=HttpUrl(href),
        )

        await context.push_data(listing.model_dump())

    # Handle pagination
    page_count = await _parse_page_count(page)
    match = re.search(r"[?&]page=(\d+)", current_url)
    current_page = int(match.group(1)) if match else 1

    if current_page < page_count:
        base_url_part = current_url.split("?")[0]
        query_params = context.request.url.split("?")[1] if "?" in context.request.url else ""
        params: dict[str, str] = dict(p.split("=", 1) for p in query_params.split("&") if "=" in p and p)

        # Enqueue all remaining pages
        requests = []
        for page_num in range(current_page + 1, page_count + 1):
            params["page"] = str(page_num)
            page_url = f"{base_url_part}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
            logger.info(f"Adding page {page_num} to queue: {page_url}")
            requests.append(Request.from_url(page_url, label=str(OLXLabels.LISTINGS.value)))

        if requests:
            logger.info(f"Enqueueing {len(requests)} remaining pages ({current_page+1}-{page_count})")
            await context.add_requests(requests)


@label(OLXLabels.DETAIL.value)  # type: ignore
async def handle_olx_detail(context: PlaywrightCrawlingContext) -> None:
    """
    Handles OLX detail pages. Extracts information like title, price,
    description, photos, and ID.
    """
    page = context.page
    url = context.request.url
    logger.info(f"Processing detail page: {url}")

    original_id = None

    # --- Try extracting ID from footer bar first ---
    try:
        footer_bar_locator = page.locator('div[data-cy="ad-footer-bar-section"] span.css-w85dhy')
        if await footer_bar_locator.count() > 0:
            id_text = await footer_bar_locator.first.inner_text()
            match = re.search(r"ID:\s*(\d+)", id_text)
            if match:
                original_id = match.group(1)
                logger.debug(f"Extracted ID from footer bar: {original_id}")
    except Exception as e:
        logger.debug(f"Could not extract ID from footer bar: {e}")

    # --- Fallback to JSON-LD if ID not found in footer ---
    if not original_id:
        logger.debug("ID not found in footer, trying JSON-LD script.")
        json_ld_scripts = page.locator('script[type="application/ld+json"]')
        for i in range(await json_ld_scripts.count()):
            try:
                script_content = await json_ld_scripts.nth(i).inner_text()
                if script_content:
                    data = json.loads(script_content)
                    if data.get("@type") == "Product" and "sku" in data:
                        original_id = data["sku"]
                        logger.debug(f"Extracted ID from JSON-LD: {original_id}")
                        break
            except Exception as e:
                logger.debug(f"Failed to parse JSON-LD script: {str(e)}")
                continue

    if not original_id:
        logger.error(f"Could not extract listing ID for {url}")
        return

    # --- Extract Core Information ---
    title = await page.locator('[data-cy="ad_title"] h4').inner_text()
    price_text = await page.locator('div[data-testid="ad-price-container"] h3[class^="css-"]').inner_text()
    price_str, price_value = _parse_price(price_text)

    # Fetch parsed_ids inside the async function
    parsed_ids = (await get_already_crawled()).get(SITE, {})

    if original_id in parsed_ids:
        if parsed_ids[original_id].content_hash == simple_hash(title, price_str):
            if parsed_ids[original_id].more:
                logger.debug(f"Skipping duplicate listing with same content: {original_id}")
                return

    description = await _parse_description(page)
    photo_urls = await _parse_photos(page)

    parameters = {}
    param_locators = page.locator('div[data-testid="ad-parameters-container"] p')
    param_count = await param_locators.count()
    for i in range(param_count):
        param_text = await param_locators.nth(i).inner_text()
        parts = param_text.split(":", 1)
        # Field: Value
        if len(parts) == 2:
            key = parts[0].strip()
            value = parts[1].strip()
            parameters[key] = value
        # Field
        elif len(parts) == 1 and parts[0].strip():
            # Store flag-like parameters as a string instead of boolean
            parameters[parts[0].strip()] = "True"

    listing_data = ListingDocument(
        original_id=original_id,
        site="olx",
        title=title.strip(),
        link=HttpUrl(url),
        price_str=price_str,
        price_value=price_value,
        description=description,
        photo_urls=photo_urls,
        parameters=parameters,
        more=False,
    )

    logger.debug(f"Successfully parsed detail page: {original_id} - {listing_data.title}")
    # Log the data just before pushing
    logger.debug(f"Pushing data for {original_id}: {listing_data.model_dump()}")
    await context.push_data(listing_data.model_dump())
