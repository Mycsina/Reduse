import logging
import os
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)


API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


# Get API key from environment
API_KEY = os.getenv("API_KEY", "")


async def verify_api_key(api_key: Optional[str] = Depends(api_key_header)):
    """Verify the API key."""
    if api_key is None:
        raise HTTPException(status_code=403, detail="No API key supplied")
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
