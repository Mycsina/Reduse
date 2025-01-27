from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright
import asyncio
from typing import Optional, Dict
import logging


class PlaywrightPool:
    """A pool of Playwright browser instances that can be acquired using async with.

    Usage:
        pool = PlaywrightPool(max_browsers=5)
        async with pool.acquire() as browser:
            # Use browser here
    """

    def __init__(self, max_browsers: int = 5):
        self.max_browsers = max_browsers
        self._semaphore = asyncio.Semaphore(max_browsers)
        self._available_browsers: asyncio.Queue[BrowserContext] = asyncio.Queue()
        self._active_browsers: Dict[BrowserContext, Browser] = {}
        self._playwright: Optional[Playwright] = None
        self.logger = logging.getLogger(__name__)
        self._initialized = False
        self._lock = asyncio.Lock()

    async def _initialize(self):
        """Initialize the Playwright instance if not already initialized."""
        if not self._initialized:
            async with self._lock:
                if not self._initialized:
                    self._playwright = await async_playwright().start()
                    self._initialized = True

    async def _create_browser(self) -> tuple[Browser, BrowserContext]:
        """Create a new browser instance and context."""
        await self._initialize()
        if not self._playwright:
            raise Exception("Playwright not initialized")
        browser = await self._playwright.firefox.launch(headless=True)
        context = await browser.new_context()
        return browser, context

    async def acquire(self):
        """Acquire a browser context from the pool or create a new one."""
        return _BrowserContextManager(self)

    async def _acquire_context(self) -> BrowserContext:
        """Internal method to acquire a browser context."""
        await self._semaphore.acquire()
        try:
            # Try to get an available browser from the pool
            context = self._available_browsers.get_nowait()
            self.logger.debug("Reusing existing browser from pool")
            return context
        except asyncio.QueueEmpty:
            # Create a new browser if none available
            self.logger.debug("Creating new browser instance")
            browser, context = await self._create_browser()
            self._active_browsers[context] = browser
            return context

    async def _release_context(self, context: BrowserContext):
        """Release a browser context back to the pool."""
        try:
            await self._available_browsers.put(context)
        finally:
            self._semaphore.release()

    async def cleanup(self):
        """Clean up all browser instances and Playwright."""
        self.logger.info("Cleaning up browser pool")
        # Close all available browsers
        while True:
            try:
                context = self._available_browsers.get_nowait()
                browser = self._active_browsers.pop(context, None)
                if browser:
                    await context.close()
                    await browser.close()
            except asyncio.QueueEmpty:
                break

        # Close all active browsers
        for context, browser in self._active_browsers.items():
            await context.close()
            await browser.close()
        self._active_browsers.clear()

        # Stop Playwright
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
            self._initialized = False


class _BrowserContextManager:
    """Context manager for acquiring and releasing browser contexts."""

    def __init__(self, pool: PlaywrightPool):
        self.pool = pool
        self.context: Optional[BrowserContext] = None

    async def __aenter__(self) -> BrowserContext:
        self.context = await self.pool._acquire_context()
        return self.context

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            await self.pool._release_context(self.context)


# Global pool instance
_pool: Optional[PlaywrightPool] = None


def get_pool(max_browsers: int = 5) -> PlaywrightPool:
    """Get or create the global browser pool."""
    global _pool
    if _pool is None:
        _pool = PlaywrightPool(max_browsers)
    return _pool


async def cleanup_pool():
    """Clean up the global browser pool."""
    global _pool
    if _pool:
        await _pool.cleanup()
        _pool = None
