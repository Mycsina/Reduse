"""Main FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import analysis, query, scrape
from .utils.logging_config import setup_logging

# Configure logging
setup_logging()

# Create FastAPI app
app = FastAPI(
    title="Vroom Backend",
    description="Backend API for Vroom - Vehicle Research and Organization Management",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize database
@app.on_event("startup")
async def startup():
    await init_db()


# Add routers
app.include_router(scrape.router, tags=["scraping"])
app.include_router(analysis.router, tags=["analysis"])
app.include_router(query.router, tags=["listings"])
app.include_router(query.analyzed_router, tags=["analyzed listings"])
