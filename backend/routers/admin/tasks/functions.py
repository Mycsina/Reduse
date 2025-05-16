"""Function introspection endpoints"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException

from backend.tasks.function_introspection import FunctionInfo, introspect

# Initialize logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/functions", tags=["introspection"])

# Initialize function discovery with specific modules to search
# This focuses the search on modules more likely to contain schedulable functions
functionDiscovery = introspect("backend")
logger.info(f"Function discovery initialized in router")


@router.get("/", response_model=List[FunctionInfo])
async def list_available_functions():
    """List all available functions that can be scheduled."""
    logger.info("Listing available functions")
    funcs = functionDiscovery.list_functions()
    logger.info(f"Found {len(funcs)} available functions")
    return [info for _, info in funcs.items()]


@router.get("/{function_path}", response_model=FunctionInfo)
async def get_function_info(function_path: str):
    """Get information about a specific function."""
    logger.info(f"Getting info for function: {function_path}")
    info = functionDiscovery.get_function_info(function_path)
    if not info:
        logger.warning(f"Function not found: {function_path}")
        raise HTTPException(status_code=404, detail=f"Function {function_path} not found")
    return info
