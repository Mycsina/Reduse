from decimal import Decimal
from typing import Optional, Any

from bson import Decimal128


def _to_decimal(v: Any) -> Optional[Decimal]:
    if isinstance(v, Decimal128):
        return Decimal(v.to_decimal())
    if isinstance(v, Decimal):
        return v
    raise ValueError(f"Invalid type for _to_decimal: {type(v)}")
