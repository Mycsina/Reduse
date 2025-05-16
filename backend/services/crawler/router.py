# backend/services/crawler/router.py
import importlib
import logging
import os
from collections.abc import Awaitable
from typing import Callable

from crawlee.crawlers import PlaywrightCrawlingContext
from crawlee.router import Router

from backend.services.crawler.handlers.handlers import default_handler

logger = logging.getLogger(__name__)


class RouterWrapper:
    def __init__(self):
        self.router = Router[PlaywrightCrawlingContext]()
        self._initialized = False

    def get_router(self) -> Router:
        if not self._initialized:
            self.router._default_handler = default_handler
            self.register_routes()
        return self.router

    def register_routes(self) -> None:
        # Get the path to the handlers directory relative to this file
        handlers_dir = os.path.join(os.path.dirname(__file__), "handlers")
        # The package path to the handlers directory
        handlers_package = "backend.services.crawler.handlers"

        logger.debug(f"Looking for handlers in: {handlers_dir}")

        # Ensure the handlers directory exists
        if not os.path.isdir(handlers_dir):
            logger.warning(f"Handlers directory not found: {handlers_dir}")
            self._initialized = True
            return

        ## Import modules in handlers folder, parse their label metadata and register them with the router
        for filename in os.listdir(handlers_dir):
            # Look for Python files, excluding __init__.py
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = filename[:-3]
                try:
                    # Import the module relative to the handlers package
                    module = importlib.import_module(f".{module_name}", package=handlers_package)
                    logger.debug(f"Successfully imported handler module: {module_name}")
                    for attr in dir(module):
                        obj = getattr(module, attr)
                        # Check if the object is a callable handler function with a 'label'
                        if callable(obj) and hasattr(obj, "label"):
                            logger.debug(f"Registering handler '{obj.label}' from {module_name}.{attr}")
                            self._add_handler(obj.label, obj)
                except ImportError as e:
                    logger.error(f"Failed to import handler module {module_name}: {e}")
                except Exception as e:
                    logger.error(f"Error processing handler module {module_name}: {e}")

        self._initialized = True

    def _add_handler(self, label: str, handler: Callable[[PlaywrightCrawlingContext], Awaitable]) -> None:
        self.router._handlers_by_label[label] = handler
