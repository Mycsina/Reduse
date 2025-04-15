# Here we define functions that integrate with external services, supporting the crawler

import hashlib
from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel

from ...schemas.listings import ListingDocument


class CrawledListing(BaseModel):
    timestamp: datetime
    content_hash: str
    more: bool


# Module-level cache
_crawled_data_cache: Optional[Dict[str, Dict[str, CrawledListing]]] = None


def simple_hash(title: str, price_str: str) -> str:
    return hashlib.sha256(f"{title}|{price_str}".encode("utf-8")).hexdigest()


async def get_already_crawled() -> Dict[str, Dict[str, CrawledListing]]:
    """
    Gets all parsed IDs, sites, timestamps, and a basic content hash from the database.

    The content hash is generated on-the-fly using the 'title' and 'price_str' fields.

    Returns:
        Dict[str, Dict[str, Tuple[datetime, str]]]: A nested dictionary where the outer
                                        key is the site and the inner key is the
                                        original_id. The value is a tuple containing
                                        the timestamp and the content hash (SHA256 hex digest).
                                        Example: {'site_a': {'id_1': (timestamp1, hash1), 'id_2': (timestamp2, hash2)}}
    """
    global _crawled_data_cache
    if _crawled_data_cache is not None:
        return _crawled_data_cache

    class ListingProjection(BaseModel):
        original_id: str
        site: str
        timestamp: datetime
        title: str
        price_str: str
        more: bool

    listings = await ListingDocument.find().project(ListingProjection).to_list()

    lookup_dict: Dict[str, Dict[str, CrawledListing]] = {}
    for listing in listings:
        site = listing.site
        original_id = listing.original_id
        timestamp = listing.timestamp

        content_hash = simple_hash(listing.title, listing.price_str)

        if site not in lookup_dict:
            lookup_dict[site] = {}
        lookup_dict[site][original_id] = CrawledListing(
            timestamp=timestamp, content_hash=content_hash, more=listing.more
        )

    _crawled_data_cache = lookup_dict
    return lookup_dict
