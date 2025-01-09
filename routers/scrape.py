import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import HttpUrl

from ..logic import scraping
from ..security import verify_api_key

router = APIRouter(prefix="/scrape")

logger = logging.getLogger(__name__)


@router.post("/olx")
async def parse_olx_categories(background_tasks: BackgroundTasks, api_key: str = Depends(verify_api_key)):
    """Parse all OLX categories and save listings without details."""
    logger.info("Starting OLX category parsing")
    background_tasks.add_task(scraping.scrape_olx_categories)
    return {"message": "OLX category parsing started."}


@router.post("/")
async def scrape(url: HttpUrl, background_tasks: BackgroundTasks, api_key: str = Depends(verify_api_key)):
    """Scrape a URL, save listings with details, and analyze them."""
    logger.info(f"Scraping {url} with details and analysis")
    background_tasks.add_task(scraping.scrape_analyze_and_save, str(url))
    return {"message": "Scraping, saving, and analysis started."}
