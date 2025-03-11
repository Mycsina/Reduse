"""Admin routes for scraping operations."""

import asyncio
import json
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, HttpUrl

from ...logic import analysis, scraping
from ...security import verify_api_key

router = APIRouter()
logger = logging.getLogger(__name__)


class QueuedTaskResponse(BaseModel):
    """Response model for endpoints that start a background task."""

    message: str
    queue_id: str


class ScrapingTaskRequest(BaseModel):
    """Request model for running a scraping task with optional analysis."""

    url: HttpUrl
    run_analysis: bool = True


@router.post("/olx-categories", response_model=QueuedTaskResponse)
async def parse_olx_categories(background_tasks: BackgroundTasks, _: str = Depends(verify_api_key)):
    """Admin endpoint to trigger OLX categories parsing."""
    queue_id = f"olx-categories-{id(background_tasks)}"

    async def process_categories():
        try:
            await scraping.scrape_olx_categories()
            logger.info("OLX categories scraping completed")
        except Exception as e:
            logger.error(f"Error scraping OLX categories: {e}")

    background_tasks.add_task(process_categories)
    return QueuedTaskResponse(
        message="OLX categories scraping started",
        queue_id=queue_id,
    )


@router.post("/url-with-analysis", response_model=QueuedTaskResponse)
async def scrape_and_analyze(
    request: ScrapingTaskRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_api_key),
):
    """Admin endpoint to scrape a URL and then analyze all listings."""
    queue_id = f"scrape-analyze-{id(background_tasks)}"
    url = str(request.url)

    async def process_pipeline():
        try:
            logger.info(f"Starting scraping and analysis pipeline for {url}")
            
            # Step 1: Scrape listings
            listings = await scraping.scrape_and_save(url)
            
            if not listings:
                logger.info("No listings found to process")
                return
            
            # Step 2: Analyze listings if requested
            if request.run_analysis:
                logger.info(f"Starting analysis of {len(listings)} listings")
                await analysis.analyze_new_listings()
                logger.info("Analysis complete")
            
            logger.info("Processing pipeline complete")
        except Exception as e:
            logger.error(f"Error in scrape and analyze pipeline: {str(e)}")

    background_tasks.add_task(process_pipeline)
    return QueuedTaskResponse(
        message=f"Started scrape and analyze pipeline for {url}",
        queue_id=queue_id,
    )


@router.post("/bulk", response_model=QueuedTaskResponse)
async def bulk_scrape(
    urls: List[HttpUrl], 
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_api_key)
):
    """Admin endpoint to scrape multiple URLs in bulk."""
    queue_id = f"bulk-scrape-{id(background_tasks)}"
    
    async def process_bulk():
        try:
            logger.info(f"Starting bulk scrape of {len(urls)} URLs")
            
            for i, url in enumerate(urls):
                try:
                    url_str = str(url)
                    logger.info(f"Processing URL {i+1}/{len(urls)}: {url_str}")
                    await scraping.scrape_and_save(url_str)
                except Exception as e:
                    logger.error(f"Error processing URL {url}: {str(e)}")
            
            logger.info("Bulk scraping complete")
        except Exception as e:
            logger.error(f"Error in bulk scraping: {str(e)}")
    
    background_tasks.add_task(process_bulk)
    return QueuedTaskResponse(
        message=f"Started bulk scraping of {len(urls)} URLs",
        queue_id=queue_id
    ) 