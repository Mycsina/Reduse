"""Filtering schemas."""

from enum import StrEnum
from typing import List, Optional, Union

from pydantic import BaseModel, Field


class FilterGroupType(StrEnum):
    """Type of filter group."""

    AND = "AND"
    OR = "OR"


class Operator(StrEnum):
    """Operators for filter conditions."""

    # String operators
    EQUALS = "EQUALS"  # Exact match (case-insensitive)
    CONTAINS = "CONTAINS"  # Contains substring (case-insensitive)
    REGEX = "REGEX"  # Direct regex pattern

    # Numerical/Date operators (TODO: Add Date support later if needed)
    GT = "GT"  # Greater than
    LT = "LT"  # Less than
    GTE = "GTE"  # Greater than or equal to
    LTE = "LTE"  # Less than or equal to
    EQ_NUM = "EQ_NUM"  # Numerical equals


class FilterCondition(BaseModel):
    """Model for a single filter condition."""

    field: str
    operator: Operator = (
        Operator.CONTAINS
    )  # Default to CONTAINS for backward compatibility/ease of use
    value: str  # Renamed from pattern


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


class SavedListingQueryItems(BaseModel):
    """Query model for saved favorite searches, omitting pagination fields."""

    price: Optional[PriceFilter] = None
    search_text: Optional[str] = None
    filter: Optional[FilterGroup] = None

    class Config:
        # Ensure that if extra fields (like skip/limit from an older version) are present,
        # they are ignored and not part of the model.
        # Pydantic v2 uses model_config with extra = 'ignore'
        # For Pydantic v1, this is extra = Extra.ignore
        # Assuming Pydantic v2 style from StrEnum, will use model_config
        # If this causes an error, it means Pydantic v1 is in use.
        # For now, let's assume model_config is available.
        # If not, we can remove this Config or adjust to Pydantic v1.
        # Update: Pydantic BaseModel itself handles this well by default for defined fields.
        # No explicit extra='ignore' needed just for omitting fields.
        pass
