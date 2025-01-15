"""Main FastAPI application."""

import logging
from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import analysis, query, scrape, schedule
from .routers.schedule import scheduler
from .utils.logging_config import setup_logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler.start()
    yield


# Create FastAPI app
app = FastAPI(
    title="Vroom Backend",
    description="Backend API",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add routers
app.include_router(scrape.router, tags=["scraping"])
app.include_router(analysis.router, tags=["analysis"])
app.include_router(query.router, tags=["listings"])
app.include_router(query.analyzed_router, tags=["analyzed listings"])
app.include_router(schedule.router)
