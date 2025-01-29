"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import analysis, analytics, query, schedule, scrape
from .tasks.scheduler import start_scheduler
from .utils.logging_config import (
    EndpointLoggingRoute,
    RequestLoggingMiddleware,
    setup_endpoint_logging,
    setup_logging,
)

# Initialize logger
logger = logging.getLogger(__name__)

# Set up logging
setup_logging()

# Set up endpoint logging
setup_endpoint_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application")
    await init_db()
    start_scheduler()
    yield
    logger.info("Shutting down application")


# Create FastAPI app with custom route class
app = FastAPI(
    title="Vroom",
    version="0.1.0",
    route_class=EndpointLoggingRoute,  # Use custom route class for logging
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

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Include routers
app.include_router(analysis.router)
app.include_router(analytics.router)
app.include_router(query.router)
app.include_router(schedule.router)
app.include_router(scrape.router)
