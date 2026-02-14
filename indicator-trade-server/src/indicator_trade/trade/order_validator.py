"""Pre-execution validation (technical validation, not risk management)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from pydantic import BaseModel

if TYPE_CHECKING:
    from indicator_trade.models.order import OrderRequest

logger = structlog.get_logger()

VALID_ACTIONS = {"OPEN_LONG", "OPEN_SHORT", "CLOSE", "ADD", "REDUCE"}
VALID_SIDES = {"buy", "sell"}
VALID_POS_SIDES = {"long", "short"}
VALID_ORDER_TYPES = {"market", "limit"}


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
        errors: list[str] = []

        self._validate_action(request, errors)
        self._validate_side(request, errors)
        self._validate_pos_side(request, errors)
        self._validate_order_type(request, errors)
        self._validate_size(request, errors)
        self._validate_leverage(request, errors)
        self._validate_limit_price(request, errors)
        self._validate_sl_tp(request, errors)

        valid = len(errors) == 0
        if not valid:
            logger.warning("order_validation_failed", errors=errors, symbol=request.symbol)

        return ValidationResult(valid=valid, errors=errors)

    def _validate_action(self, request: OrderRequest, errors: list[str]) -> None:
        if request.action not in VALID_ACTIONS:
            errors.append(f"Invalid action '{request.action}'. Must be one of {VALID_ACTIONS}")

    def _validate_side(self, request: OrderRequest, errors: list[str]) -> None:
        if request.side not in VALID_SIDES:
            errors.append(f"Invalid side '{request.side}'. Must be one of {VALID_SIDES}")

    def _validate_pos_side(self, request: OrderRequest, errors: list[str]) -> None:
        if request.pos_side not in VALID_POS_SIDES:
            errors.append(
                f"Invalid pos_side '{request.pos_side}'. Must be one of {VALID_POS_SIDES}"
            )

    def _validate_order_type(self, request: OrderRequest, errors: list[str]) -> None:
        if request.order_type not in VALID_ORDER_TYPES:
            errors.append(
                f"Invalid order_type '{request.order_type}'. Must be one of {VALID_ORDER_TYPES}"
            )

    def _validate_size(self, request: OrderRequest, errors: list[str]) -> None:
        if not request.size:
            errors.append("size is required and cannot be empty")
            return
        try:
            size = float(request.size)
            if size <= 0:
                errors.append(f"size must be > 0, got {request.size}")
        except ValueError:
            errors.append(f"size must be a valid number, got '{request.size}'")

    def _validate_leverage(self, request: OrderRequest, errors: list[str]) -> None:
        try:
            lever = float(request.leverage)
            if lever <= 0:
                errors.append(f"leverage must be > 0, got {request.leverage}")
        except ValueError:
            errors.append(f"leverage must be a valid number, got '{request.leverage}'")

    def _validate_limit_price(self, request: OrderRequest, errors: list[str]) -> None:
        if request.order_type != "limit":
            return
        if not request.limit_price:
            errors.append("limit_price is required for limit orders")
            return
        try:
            price = float(request.limit_price)
            if price <= 0:
                errors.append(f"limit_price must be > 0, got {request.limit_price}")
        except ValueError:
            errors.append(f"limit_price must be a valid number, got '{request.limit_price}'")

    def _validate_sl_tp(self, request: OrderRequest, errors: list[str]) -> None:
        """Validate SL/TP logical correctness relative to entry price."""
        # Only validate if we have an entry price reference (limit orders)
        if not request.limit_price:
            return

        try:
            entry = float(request.limit_price)
        except (ValueError, TypeError):
            return

        is_long = request.pos_side == "long"

        if request.stop_loss:
            try:
                sl = float(request.stop_loss)
                if is_long and sl >= entry:
                    errors.append(f"stop_loss ({sl}) must be < entry ({entry}) for long positions")
                elif not is_long and sl <= entry:
                    errors.append(f"stop_loss ({sl}) must be > entry ({entry}) for short positions")
            except (ValueError, TypeError):
                errors.append(f"stop_loss must be a valid number, got '{request.stop_loss}'")

        if request.take_profit:
            try:
                tp = float(request.take_profit)
                if is_long and tp <= entry:
                    errors.append(
                        f"take_profit ({tp}) must be > entry ({entry}) for long positions"
                    )
                elif not is_long and tp >= entry:
                    errors.append(
                        f"take_profit ({tp}) must be < entry ({entry}) for short positions"
                    )
            except (ValueError, TypeError):
                errors.append(f"take_profit must be a valid number, got '{request.take_profit}'")
