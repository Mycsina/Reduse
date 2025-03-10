"""Function introspection endpoints"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...security import verify_api_key
from ...tasks.function_introspection import FunctionInfo, introspect

# Initialize logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/functions", tags=["introspection"])

functionDiscovery = introspect()

@router.get("/functions", response_model=List[FunctionInfo])
async def list_available_functions(_: str = Depends(verify_api_key)):
    """List all available functions that can be scheduled."""
    funcs = functionDiscovery.list_functions()
    return [info for _, info in funcs.items()]


@router.get("/functions/{function_path}", response_model=FunctionInfo)
async def get_function_info(function_path: str, _: str = Depends(verify_api_key)):
    """Get information about a specific function."""
    info = functionDiscovery.get_function_info(function_path)
    if not info:
        raise HTTPException(status_code=404, detail=f"Function {function_path} not found")
    return info
