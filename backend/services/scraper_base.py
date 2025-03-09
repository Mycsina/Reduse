# scrappers/scraper_base.py
import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Type, runtime_checkable
from urllib.parse import urlparse

from ..schemas.listings import \
    ListingDocument  # Adjust import based on actual location


class ScraperError(Exception):
    """Base class for scraper errors."""


class ScraperNotFoundError(ScraperError):
    """Raised when no scraper is found for a given URL."""


@runtime_checkable
class Scraper(Protocol):
    @classmethod
    def can_handle(cls, url: str) -> bool:
        """Check if this scraper can handle the given URL"""
        ...

    async def scrape(
        self, url: str, already_scraped_ids: Optional[List[str]] = None
    ) -> List[ListingDocument]:
        """Scrape the URL and return the results"""
        ...

    @classmethod
    def _get_site_from_url(cls, url: str) -> str:
        """Extract site name from URL."""
        try:
            domain = urlparse(url).netloc
            # Remove www. and get the main domain
            return domain.replace("www.", "").split(".")[0]
        except Exception:
            return "unknown"


class ScraperRegistry:
    _scrapers: Dict[str, Type["Scraper"]] = {}

    def __init__(self):
        """
        Initializes the ScraperRegistry and automatically discovers and registers scrapers
        within the same directory.
        """
        self._discover_scrapers()

    def _discover_scrapers(self) -> None:
        """
        Discovers and registers Scraper subclasses in the current directory.
        """
        current_dir = Path(__file__).parent  # Get the directory of scraper_base.py

        for file_path in current_dir.glob("*.py"):
            module_name = file_path.stem
            if (
                module_name != "__init__" and module_name != Path(__file__).stem
            ):  # Exclude __init__.py and self
                try:
                    # Import modules within the same directory
                    module = importlib.import_module(
                        f".{module_name}", package=__package__
                    )
                    self._register_scrapers_from_module(module)
                except Exception as e:
                    import traceback

                    print(f"Error loading scraper module '{module_name}': {e}")
                    traceback.print_exc()

    def _register_scrapers_from_module(self, module) -> None:
        """
        Registers Scraper subclasses found within a module.
        """
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and issubclass(obj, Scraper) and obj != Scraper:
                # Use the class name as a default "name" for the scraper
                self.register(obj.__name__, obj)
                print(
                    f"Registered scraper: {obj.__name__} from module {module.__name__}"
                )

    def register(self, name: str, scraper_class: Type["Scraper"]) -> None:
        """Registers a scraper class."""
        self._scrapers[name] = scraper_class

    def get_scraper(self, url: str) -> Type["Scraper"]:
        """Returns the appropriate scraper class for the given URL."""
        domain = urlparse(url).netloc
        for scraper_class in self._scrapers.values():
            if scraper_class.can_handle(url):
                return scraper_class
        raise ScraperNotFoundError(f"No scraper available for {domain}")
