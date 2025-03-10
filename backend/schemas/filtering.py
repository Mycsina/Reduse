"""Filtering schemas."""

from enum import StrEnum
from typing import List, Optional, Union

from pydantic import BaseModel, Field


class FilterGroupType(StrEnum):
    """Type of filter group."""

    AND = "AND"
    OR = "OR"


class FilterCondition(BaseModel):
    """Model for a single filter condition."""

    field: str
    pattern: str


class FilterGroup(BaseModel):
    """Model for a group of filter conditions."""

    type: FilterGroupType
    conditions: List[Union[FilterCondition, "FilterGroup"]]


class PriceFilter(BaseModel):
    """Price filter model."""

    min: Optional[float] = None
    max: Optional[float] = None


class ListingQuery(BaseModel):
    """Query model for standard listing queries."""

    price: Optional[PriceFilter] = None
    search_text: Optional[str] = None
    filter: Optional[FilterGroup] = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=12, ge=1, le=100)
