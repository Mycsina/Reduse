import logging
import os
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from backend.auth import current_active_user, current_superuser
from backend.schemas.users import User

logger = logging.getLogger(__name__)


API_KEY_NAME = "X-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

API_KEY = os.getenv("API_KEY", "")


async def verify_security_api_key(
    api_key: Optional[str] = Depends(api_key_header),
):
    """Verifies that the request is properly authenticated with an API key."""
    if api_key is None:
        raise HTTPException(status_code=403, detail="No API key supplied")
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")


async def verify_security(
    _=Depends(current_active_user),
):
    """Verifies that the request is properly authenticated."""
    pass


async def verify_security_admin(_=Depends(current_superuser)):
    """Verifies that the request is properly authenticated with admin privileges."""
    pass
