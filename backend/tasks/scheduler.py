"""Task scheduler for periodic jobs."""

import asyncio
import logging
from datetime import datetime

from ..services.analytics_service import update_model_price_stats

logger = logging.getLogger(__name__)


async def run_analytics_update():
    """Run analytics update task."""
    try:
        num_stats = await update_model_price_stats()
        logger.info(f"Created {num_stats} price statistics at {datetime.utcnow()}")
    except Exception as e:
        logger.error(f"Failed to update analytics: {str(e)}")


async def schedule_analytics_updates(interval_hours: int = 1):
    """Schedule periodic analytics updates."""
    while True:
        await run_analytics_update()
        await asyncio.sleep(interval_hours * 3600)  # Convert hours to seconds


def start_scheduler():
    """Start the task scheduler."""
    loop = asyncio.get_event_loop()
    loop.create_task(schedule_analytics_updates())
