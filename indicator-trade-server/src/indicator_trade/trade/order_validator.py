"""Pre-execution validation (technical validation, not risk management)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from pydantic import BaseModel

if TYPE_CHECKING:
    from indicator_trade.models.order import OrderRequest

logger = structlog.get_logger()


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str] = []


class OrderValidator:
    """
    Pre-execution validation:
    - Required fields present
    - Size > 0 and valid format
    - Limit price valid for limit orders
    - SL < entry for LONG, SL > entry for SHORT
    - TP > entry for LONG, TP < entry for SHORT
    """

    def validate(self, request: OrderRequest) -> ValidationResult:
        """Run all validation checks. Returns ValidationResult."""
        ...
