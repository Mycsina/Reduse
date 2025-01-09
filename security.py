# Initialize API key header
import os
from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader


API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verify the API key."""
    if api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
