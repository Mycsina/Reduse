"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from fastapi_mcp import add_mcp_server

logger = logging.getLogger(__name__)


from .db import init_db
from .routers.analysis import router as analysis_router
from .routers.analytics import router as analytics_router
from .routers.query import router as query_router
from .routers.scrape import router as scrape_router
from .routers.tasks import router as tasks_router
from .routers.bug_reports import router as bug_reports_router
from .tasks.function_introspection import introspect
from .tasks.scheduler import start_scheduler
from .utils.logging_config import EndpointLoggingRoute, RequestLoggingMiddleware, setup_endpoint_logging, setup_logging
from .config import settings  # Import settings

# Set up logging
setup_logging()

# Set up endpoint logging
setup_endpoint_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application")

    # Initialize database first
    await init_db()

    logger.info("Starting function discovery...")
    discovery = introspect()
    discovery.discover_functions(
        exclude_patterns=[
            "backend.services.crawler.routes.*",
            "backend.services.crawler.*",
        ]
    )
    logger.info(f"Function discovery completed. Found {len(discovery.list_functions())} functions.")

    start_scheduler()
    yield
    logger.info("Shutting down application")


# Determine route class based on settings
route_class = EndpointLoggingRoute if settings.logging.enable_endpoint_logging else APIRoute

# Create FastAPI app with custom route class
app = FastAPI(
    title="Reduse",
    version="0.1.0",
    route_class=route_class,  # Use determined route class
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware conditionally
if settings.logging.enable_endpoint_logging:
    app.add_middleware(RequestLoggingMiddleware)

# Include routers
app.include_router(analysis_router)
app.include_router(analytics_router)
app.include_router(query_router)
app.include_router(tasks_router)
app.include_router(scrape_router)
app.include_router(bug_reports_router)

add_mcp_server(
    app,                    # Your FastAPI app
    mount_path="/mcp",      # Where to mount the MCP server
    name="Reduse API MCP",      # Name for the MCP server
)