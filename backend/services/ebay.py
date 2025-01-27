"""eBay API scraper implementation."""

import logging
from decimal import Decimal
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

import httpx
from beanie import Document

from ..config import settings
from ..schemas.listings import ListingDocument
from ..utils.oauth import OAuthManager
from .scraper_base import Scraper


class EbayScraper(Scraper):
    """Scraper for eBay using their official API."""

    def __init__(self):
        """Initialize the eBay scraper."""
        self.logger = logging.getLogger(__name__)
        self.base_url = "https://api.ebay.com/buy/browse/v1"
        self.auth_url = "https://api.ebay.com/identity/v1/oauth2/token"
        self.client: Optional[httpx.AsyncClient] = None

        # Create OAuth manager
        app_id = settings.ebay.app_id.get_secret_value()
        cert_id = settings.ebay.cert_id.get_secret_value()
        app_credentials = settings.ebay.app_credentials.get_secret_value()

        if not app_id or not cert_id or not app_credentials:
            raise ValueError("Missing eBay API credentials")

        self.oauth = OAuthManager(
            token_url=self.auth_url,
            client_id=app_id,
            client_secret=cert_id,
            scope="https://api.ebay.com/oauth/api_scope",
        )

    @classmethod
    def can_handle(cls, url: str) -> bool:
        """Check if this scraper can handle the given URL."""
        return "ebay" in url.lower()

    async def _ensure_client(self) -> None:
        """Ensure httpx client exists."""
        if self.client is None:
            self.client = httpx.AsyncClient()
            if not self.client:
                raise RuntimeError("Failed to create httpx client")

    async def _api_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make an authenticated request to the eBay API."""
        await self._ensure_client()
        if not self.client:
            raise RuntimeError("Failed to create httpx client")

        token = await self.oauth.get_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
        }

        response = await self.client.get(f"{self.base_url}{endpoint}", params=params, headers=headers)
        if response.status_code != 200:
            raise Exception(f"API request failed: {response.text}")
        return response.json()

    def _parse_item(self, item: Dict[str, Any]) -> ListingDocument:
        """Parse an eBay item into a ListingDocument."""
        try:
            # Extract price
            price_str = item["price"]["value"]
            price_value = Decimal(price_str)

            # TODO: Parse photos

            return ListingDocument(
                original_id=item["itemId"],
                site="ebay",
                title=item["title"],
                link=item["itemWebUrl"],
                price_str=f"€{price_str}",
                price_value=price_value,
                description=item.get("shortDescription", ""),
                more=False,  # eBay API provides all needed info
            )
        except Exception as e:
            self.logger.error(f"Error parsing item {item.get('itemId', 'unknown')}: {str(e)}")
            raise

    def _extract_search_params(self, url: str) -> Dict[str, Any]:
        """Extract search parameters from eBay URL."""
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        # Extract search keywords from the URL
        search_query = ""
        if "_nkw" in query_params:
            search_query = query_params["_nkw"][0]
        elif "keywords" in query_params:
            search_query = query_params["keywords"][0]
        else:
            # If no search keywords found, use the last path component
            path_parts = [p for p in parsed_url.path.split("/") if p]
            if path_parts:
                search_query = path_parts[-1].replace("-", " ")

        return {"q": search_query, "limit": 50, "filter": "conditions:{NEW}", "sort": "price"}

    async def scrape(self, url: str, document: Document) -> None:
        """Scrape eBay listings using their API."""
        try:
            # Extract search parameters from URL
            search_params = self._extract_search_params(url)
            if not search_params["q"]:
                raise ValueError("Could not extract search query from URL")

            results = await self._api_request("item_summary/search", search_params)

            listings = []
            for item in results.get("itemSummaries", []):
                try:
                    listing = self._parse_item(item)
                    listings.append(listing)
                except Exception as e:
                    self.logger.error(f"Error processing item: {str(e)}")
                    continue

            self.logger.info(f"Successfully scraped {len(listings)} listings from eBay")
            # TODO: Update document with listings

        except Exception as e:
            self.logger.error(f"Error during eBay scraping: {str(e)}")

        finally:
            # Clean up client and OAuth manager
            if self.client:
                await self.client.aclose()
                self.client = None
            await self.oauth.close()

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()
            self.client = None
        await self.oauth.close()
