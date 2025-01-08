import os
from contextlib import asynccontextmanager
from shutil import copyfile
import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, HttpUrl

from .db import init_db
from .logic import analysis, back
from .utils.logging_config import setup_logging
from .utils.playwright_pool import cleanup_pool, get_pool

# Set up logging first, before any other imports might configure it
logger = setup_logging()

# Initialize API key header
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verify the API key."""
    if api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


class ScrapeRequest(BaseModel):
    """Request model for scrape endpoints."""


async def on_startup():
    """Initialize application dependencies."""
    logger.info("Starting application")
    await init_db()
    logger.info("Database initialized")
    get_pool()
    logger.info("Playwright pool initialized")
    if not os.path.exists(".env"):
        logger.info("Creating .env file")
        copyfile(".env.template", ".env")


async def on_shutdown():
    """Cleanup application dependencies."""
    logger.info("Shutting down application")
    await cleanup_pool()
    logger.info("Playwright pool cleaned up")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await on_startup()
    yield


app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Modify this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/test/add-listing")
async def add_listing(api_key: str = Depends(verify_api_key)):
    """Add a test listing to the database."""
    await analysis.add_test_listing()
    return {"message": "Test listing added."}


@app.post("/scrape/")
async def scrape(url: HttpUrl, background_tasks: BackgroundTasks, api_key: str = Depends(verify_api_key)):
    """Scrape a URL, save listings with details, and analyze them."""
    logger.info(f"Scraping {url} with details and analysis")
    background_tasks.add_task(back.scrape_analyze_and_save, str(url))
    return {"message": "Scraping, saving, and analysis started."}


@app.get("/analysis/status")
async def get_analysis_status(api_key: str = Depends(verify_api_key)):
    """Get the current status of listing analysis."""
    status = await analysis.get_analysis_status()
    return status


@app.post("/analysis/retry-failed")
async def retry_failed_analyses(background_tasks: BackgroundTasks, api_key: str = Depends(verify_api_key)):
    """Retry failed analyses."""
    result = await analysis.retry_failed_analyses()
    background_tasks.add_task(analysis.analyze_new_listings)

    msg = f"Retrying analysis for {len(result)} listings. "
    return {"message": msg}


@app.post("/analysis/start")
async def start_analysis(background_tasks: BackgroundTasks, api_key: str = Depends(verify_api_key)):
    """Start analysis of pending listings."""
    status = await analysis.get_analysis_status()

    if status["pending"] == 0:
        return {"message": "No pending listings to analyze.", "can_start": False, **status}

    if not status["can_process"]:
        return {
            "message": "Rate limits reached. Please try again later.",
            "can_start": False,
            **status,
        }

    background_tasks.add_task(
        analysis.analyze_new_listings,
    )
    return {
        "message": f"Starting analysis of {status['pending']} listings.",
        "can_start": True,
        **status,
    }


@app.post("/scrape/olx")
async def parse_olx_categories(background_tasks: BackgroundTasks, api_key: str = Depends(verify_api_key)):
    """Parse all OLX categories and save listings without details."""
    logger.info("Starting OLX category parsing")
    background_tasks.add_task(back.parse_olx_categories)
    return {"message": "OLX category parsing started."}


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000, reload=True)
