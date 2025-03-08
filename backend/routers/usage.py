from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from ..services import usage as usage_service
from ..security import get_current_user

router = APIRouter(prefix="/usage", tags=["usage"])


class UsageResponse(BaseModel):
    used: int
    remaining: int
    limit: int
    is_limited: bool


@router.get("/{feature}", response_model=UsageResponse)
async def get_feature_usage(feature: str, user=Depends(get_current_user)):
    """Get current usage for a feature."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Premium users have unlimited access
    if user.is_premium:
        return UsageResponse(used=0, remaining=float("inf"), limit=float("inf"), is_limited=False)

    return await usage_service.get_daily_usage(str(user.id), feature)


@router.post("/{feature}")
async def record_feature_usage(feature: str, user=Depends(get_current_user)):
    """Record usage of a feature."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Premium users don't need usage tracking
    if user.is_premium:
        return {"success": True}

    success = await usage_service.record_usage(str(user.id), feature)
    if not success:
        raise HTTPException(status_code=402, detail="Usage limit reached. Please upgrade to continue.")

    return {"success": True}
