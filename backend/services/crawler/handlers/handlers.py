from enum import Enum
from typing import Awaitable, Callable

from crawlee import Request
from crawlee.crawlers import PlaywrightCrawlingContext


class WebsiteHandler(Enum):
    OLX = "www.olx.pt"


def label(label: str):
    """Attaches label information to a method."""

    def _attach_label(
        func: Callable[[PlaywrightCrawlingContext], Awaitable],
    ) -> Callable[[PlaywrightCrawlingContext], Awaitable]:
        func.label = label
        return func

    return _attach_label


async def default_handler(context: PlaywrightCrawlingContext) -> None:
    url = context.request.url
    if WebsiteHandler.OLX.value in url:
        await context.add_requests([Request.from_url(url, label=WebsiteHandler.OLX.value, always_enqueue=True)])
