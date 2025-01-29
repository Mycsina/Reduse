"""Query schemas."""

from enum import StrEnum
from typing import List, Union

from pydantic import BaseModel


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
