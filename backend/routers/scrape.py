"""Scraping endpoints."""

import asyncio
import json
import logging
from typing import Any

from fastapi import (APIRouter, BackgroundTasks, Depends, Header,
                     HTTPException, Query)
from pydantic import BaseModel, HttpUrl
from sse_starlette.sse import EventSourceResponse

from ..logic import scraping
from ..security import API_KEY, verify_api_key

router = APIRouter(prefix="/scrape")
logger = logging.getLogger(__name__)

# Simple queue storage
queues = {}


def create_sse_message(type_: str, data: Any) -> str:
    """Create a standardized SSE message."""
    return json.dumps({"type": type_, "data": data})


class LogHandler(logging.Handler):
    def __init__(self, queue_id: str):
        super().__init__()
        self.queue = asyncio.Queue()
        queues[queue_id] = self.queue
        # Capture all logs
        self.setLevel(logging.INFO)

    def emit(self, record):
        try:
            # Format the log message with module name
            log_entry = f"[{record.name}] {self.format(record)}"
            # Put it in the queue
            asyncio.create_task(self.queue.put({"type": "log", "message": log_entry}))
        except Exception:
            self.handleError(record)


async def send_progress(queue_id: str, phase: str, current: int, total: int):
    """Send progress update."""
    if queue_id in queues:
        await queues[queue_id].put(
            {"type": "progress", "phase": phase, "current": current, "total": total}
        )


class ScrapeRequest(BaseModel):
    """Request model for scraping a URL."""

    url: HttpUrl


class QueuedTaskResponse(BaseModel):
    """Response model for endpoints that start a background task."""

    message: str
    queue_id: str


async def verify_api_key_sse(
    api_key: str = Query(None), x_api_key: str | None = Header(None, alias="X-API-Key")
):
    """Verify API key from either query param or header for SSE endpoints."""
    if api_key == API_KEY or x_api_key == API_KEY:
        return True
    raise HTTPException(status_code=403, detail="Invalid API key")


@router.get("/logs/{queue_id}")
async def stream_logs(
    queue_id: str, _: bool = Depends(verify_api_key_sse)
) -> EventSourceResponse:
    """Stream logs for a specific scraping operation."""
    if queue_id not in queues:
        return EventSourceResponse([{"data": json.dumps({"type": "error", "message": "Queue not found"})}])  # type: ignore # noqa: E501

    async def event_generator():
        try:
            while True:
                message = await queues[queue_id].get()
                yield {"data": json.dumps(message)}
        except asyncio.CancelledError:
            pass
        finally:
            if queue_id in queues:
                del queues[queue_id]

    return EventSourceResponse(event_generator())


@router.post("/", response_model=QueuedTaskResponse)
async def scrape(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_api_key),
):
    """Scrape a URL for listings."""
    queue_id = str(id(background_tasks))
    handler = LogHandler(queue_id)

    # Add handler to root logger to capture all module logs
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    url = str(request.url)
    logger.info(f"Scrape request received for URL: {url}")

    async def process_url():
        try:
            await send_progress(queue_id, "Scraping", 0, 1)
            logger.info(f"Starting scraping for {url}")

            # Scrape and save listings
            results = await scraping.scrape_and_save(url)

            if results:
                logger.info(f"Scraped {len(results)} listings from {url}")
            else:
                logger.warning(f"No listings found at {url}")

            await send_progress(queue_id, "Scraping", 1, 1)
            logger.info("Scraping complete")

        except Exception as e:
            logger.error(f"Error scraping URL: {str(e)}")
        finally:
            root_logger.removeHandler(handler)

    background_tasks.add_task(process_url)
    return QueuedTaskResponse(message="Scraping started", queue_id=queue_id)
