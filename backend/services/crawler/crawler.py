import logging
from datetime import datetime
from typing import Dict

from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee.router import Router

logger = logging.getLogger(__name__)


class Crawler:
    # We create our own crawler class so we can have more control over what's going on
    def __init__(
        self,
        router: Router[PlaywrightCrawlingContext],
    ):
        self.router = router

    async def get_crawler(self) -> PlaywrightCrawler:
        """Creates and configures a PlaywrightCrawler instance."""

        # Initialize crawler normally
        crawler = PlaywrightCrawler(
            request_handler=self.router,
            configure_logging=False,
        )

        return crawler
