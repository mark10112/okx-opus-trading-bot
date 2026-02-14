"""Unit tests for order validator."""

from __future__ import annotations

import pytest

from indicator_trade.models.order import OrderRequest
from indicator_trade.trade.order_validator import OrderValidator


@pytest.fixture
def validator() -> OrderValidator:
    return OrderValidator()


def _make_request(**overrides) -> OrderRequest:
    defaults = {
        "action": "OPEN_LONG",
        "symbol": "BTC-USDT-SWAP",
        "side": "buy",
        "pos_side": "long",
        "order_type": "market",
        "size": "1",
        "leverage": "3",
    }
    defaults.update(overrides)
    return OrderRequest(**defaults)


# --- Valid orders ---


class TestValidOrders:
    def test_valid_market_order(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request())
        assert result.valid is True
        assert result.errors == []

    def test_valid_limit_order(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(order_type="limit", limit_price="50000"))
        assert result.valid is True

    def test_valid_close_order(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(action="CLOSE"))
        assert result.valid is True

    def test_valid_add_order(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(action="ADD"))
        assert result.valid is True

    def test_valid_reduce_order(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(action="REDUCE"))
        assert result.valid is True

    def test_valid_open_short(self, validator: OrderValidator) -> None:
        result = validator.validate(
            _make_request(action="OPEN_SHORT", side="sell", pos_side="short")
        )
        assert result.valid is True


# --- Action validation ---


class TestActionValidation:
    def test_invalid_action(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(action="INVALID"))
        assert result.valid is False
        assert any("action" in e.lower() for e in result.errors)

    def test_empty_action(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(action=""))
        assert result.valid is False


# --- Side validation ---


class TestSideValidation:
    def test_invalid_side(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(side="invalid"))
        assert result.valid is False
        assert any("side" in e.lower() for e in result.errors)

    def test_valid_sell_side(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(side="sell"))
        assert result.valid is True


# --- Pos side validation ---


class TestPosSideValidation:
    def test_invalid_pos_side(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(pos_side="invalid"))
        assert result.valid is False
        assert any("pos_side" in e.lower() for e in result.errors)

    def test_valid_short_pos_side(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(pos_side="short"))
        assert result.valid is True


# --- Order type validation ---


class TestOrderTypeValidation:
    def test_invalid_order_type(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(order_type="stop"))
        assert result.valid is False
        assert any("order_type" in e.lower() for e in result.errors)


# --- Size validation ---


class TestSizeValidation:
    def test_size_zero(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(size="0"))
        assert result.valid is False
        assert any("size" in e.lower() for e in result.errors)

    def test_size_negative(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(size="-1"))
        assert result.valid is False

    def test_size_not_numeric(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(size="abc"))
        assert result.valid is False

    def test_size_boundary_small_positive(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(size="0.001"))
        assert result.valid is True

    def test_size_empty(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(size=""))
        assert result.valid is False


# --- Limit price validation ---


class TestLimitPriceValidation:
    def test_limit_order_missing_price(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(order_type="limit", limit_price=None))
        assert result.valid is False
        assert any("limit_price" in e.lower() for e in result.errors)

    def test_limit_order_zero_price(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(order_type="limit", limit_price="0"))
        assert result.valid is False

    def test_limit_order_negative_price(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(order_type="limit", limit_price="-100"))
        assert result.valid is False

    def test_limit_order_valid_price(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(order_type="limit", limit_price="50000"))
        assert result.valid is True

    def test_market_order_ignores_limit_price(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(order_type="market", limit_price=None))
        assert result.valid is True


# --- Leverage validation ---


class TestLeverageValidation:
    def test_leverage_zero(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(leverage="0"))
        assert result.valid is False

    def test_leverage_negative(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(leverage="-1"))
        assert result.valid is False

    def test_leverage_not_numeric(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(leverage="abc"))
        assert result.valid is False

    def test_leverage_valid(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(leverage="3"))
        assert result.valid is True

    def test_leverage_boundary_small(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(leverage="0.5"))
        assert result.valid is True


# --- SL/TP validation ---


class TestStopLossTakeProfitValidation:
    def test_sl_below_entry_for_long_valid(self, validator: OrderValidator) -> None:
        result = validator.validate(
            _make_request(
                action="OPEN_LONG",
                side="buy",
                pos_side="long",
                limit_price="50000",
                order_type="limit",
                stop_loss="49000",
                take_profit="52000",
            )
        )
        assert result.valid is True

    def test_sl_above_entry_for_long_invalid(self, validator: OrderValidator) -> None:
        result = validator.validate(
            _make_request(
                action="OPEN_LONG",
                side="buy",
                pos_side="long",
                limit_price="50000",
                order_type="limit",
                stop_loss="51000",
            )
        )
        assert result.valid is False
        assert any("stop_loss" in e.lower() for e in result.errors)

    def test_sl_above_entry_for_short_valid(self, validator: OrderValidator) -> None:
        result = validator.validate(
            _make_request(
                action="OPEN_SHORT",
                side="sell",
                pos_side="short",
                limit_price="50000",
                order_type="limit",
                stop_loss="51000",
                take_profit="48000",
            )
        )
        assert result.valid is True

    def test_sl_below_entry_for_short_invalid(self, validator: OrderValidator) -> None:
        result = validator.validate(
            _make_request(
                action="OPEN_SHORT",
                side="sell",
                pos_side="short",
                limit_price="50000",
                order_type="limit",
                stop_loss="49000",
            )
        )
        assert result.valid is False

    def test_tp_below_entry_for_long_invalid(self, validator: OrderValidator) -> None:
        result = validator.validate(
            _make_request(
                action="OPEN_LONG",
                side="buy",
                pos_side="long",
                limit_price="50000",
                order_type="limit",
                take_profit="49000",
            )
        )
        assert result.valid is False
        assert any("take_profit" in e.lower() for e in result.errors)

    def test_tp_above_entry_for_short_invalid(self, validator: OrderValidator) -> None:
        result = validator.validate(
            _make_request(
                action="OPEN_SHORT",
                side="sell",
                pos_side="short",
                limit_price="50000",
                order_type="limit",
                take_profit="51000",
            )
        )
        assert result.valid is False

    def test_sl_equal_to_entry_for_long_invalid(self, validator: OrderValidator) -> None:
        result = validator.validate(
            _make_request(
                action="OPEN_LONG",
                side="buy",
                pos_side="long",
                limit_price="50000",
                order_type="limit",
                stop_loss="50000",
            )
        )
        assert result.valid is False

    def test_tp_equal_to_entry_for_long_invalid(self, validator: OrderValidator) -> None:
        result = validator.validate(
            _make_request(
                action="OPEN_LONG",
                side="buy",
                pos_side="long",
                limit_price="50000",
                order_type="limit",
                take_profit="50000",
            )
        )
        assert result.valid is False

    def test_no_sl_tp_is_valid(self, validator: OrderValidator) -> None:
        result = validator.validate(_make_request(stop_loss=None, take_profit=None))
        assert result.valid is True

    def test_sl_tp_skipped_for_market_without_price(self, validator: OrderValidator) -> None:
        # Market orders without limit_price: SL/TP validation skipped (no entry ref)
        result = validator.validate(
            _make_request(order_type="market", stop_loss="49000", take_profit="52000")
        )
        assert result.valid is True


# --- Multiple errors ---


class TestMultipleErrors:
    def test_multiple_errors_collected(self, validator: OrderValidator) -> None:
        result = validator.validate(
            _make_request(action="INVALID", side="bad", size="0", leverage="abc")
        )
        assert result.valid is False
        assert len(result.errors) >= 3
