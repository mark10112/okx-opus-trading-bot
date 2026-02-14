"""Unit tests for order executor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from indicator_trade.models.order import OrderRequest, OrderResult
from indicator_trade.trade.order_executor import OrderExecutor
from indicator_trade.trade.order_validator import OrderValidator, ValidationResult


# --- Fixtures ---


def _make_request(**overrides) -> OrderRequest:
    defaults = {
        "action": "OPEN_LONG",
        "symbol": "BTC-USDT-SWAP",
        "side": "buy",
        "pos_side": "long",
        "order_type": "market",
        "size": "1",
        "leverage": "3",
        "stop_loss": "49000",
        "take_profit": "55000",
    }
    defaults.update(overrides)
    return OrderRequest(**defaults)


@pytest.fixture
def mock_rest_client() -> AsyncMock:
    client = AsyncMock()
    client.set_leverage = AsyncMock(return_value={"code": "0", "data": [{"lever": "3"}]})
    client.place_order = AsyncMock(
        return_value=OrderResult(success=True, ord_id="ord-123")
    )
    client.place_algo_order = AsyncMock(
        return_value={"code": "0", "data": [{"algoId": "algo-1", "sCode": "0"}]}
    )
    client.close_position = AsyncMock(
        return_value={"code": "0", "data": [{"instId": "BTC-USDT-SWAP"}]}
    )
    return client


@pytest.fixture
def mock_validator() -> MagicMock:
    v = MagicMock(spec=OrderValidator)
    v.validate = MagicMock(return_value=ValidationResult(valid=True, errors=[]))
    return v


@pytest.fixture
def executor(mock_rest_client: AsyncMock, mock_validator: MagicMock) -> OrderExecutor:
    return OrderExecutor(rest_client=mock_rest_client, validator=mock_validator)


# --- Validation rejection ---


class TestValidationRejection:
    @pytest.mark.asyncio
    async def test_invalid_order_rejected(
        self, executor: OrderExecutor, mock_validator: MagicMock
    ) -> None:
        mock_validator.validate.return_value = ValidationResult(
            valid=False, errors=["size must be > 0"]
        )
        result = await executor.execute(_make_request(size="0"))
        assert result.success is False
        assert "size must be > 0" in result.error_message
        executor.rest_client.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_order_proceeds(
        self, executor: OrderExecutor, mock_validator: MagicMock
    ) -> None:
        result = await executor.execute(_make_request())
        assert result.success is True
        assert result.ord_id == "ord-123"


# --- OPEN flow ---


class TestOpenFlow:
    @pytest.mark.asyncio
    async def test_open_long_sets_leverage(
        self, executor: OrderExecutor, mock_rest_client: AsyncMock
    ) -> None:
        await executor.execute(_make_request(action="OPEN_LONG", leverage="3"))
        mock_rest_client.set_leverage.assert_called_once_with(
            "BTC-USDT-SWAP", "3"
        )

    @pytest.mark.asyncio
    async def test_open_long_places_main_order(
        self, executor: OrderExecutor, mock_rest_client: AsyncMock
    ) -> None:
        request = _make_request(action="OPEN_LONG")
        await executor.execute(request)
        mock_rest_client.place_order.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_open_long_places_algo_order_with_sl_tp(
        self, executor: OrderExecutor, mock_rest_client: AsyncMock
    ) -> None:
        request = _make_request(
            action="OPEN_LONG", stop_loss="49000", take_profit="55000"
        )
        await executor.execute(request)
        mock_rest_client.place_algo_order.assert_called_once()
        call_kwargs = mock_rest_client.place_algo_order.call_args[1]
        assert call_kwargs["slTriggerPx"] == "49000"
        assert call_kwargs["tpTriggerPx"] == "55000"

    @pytest.mark.asyncio
    async def test_open_long_no_sl_skips_algo(
        self, executor: OrderExecutor, mock_rest_client: AsyncMock
    ) -> None:
        request = _make_request(action="OPEN_LONG", stop_loss=None, take_profit=None)
        await executor.execute(request)
        mock_rest_client.place_algo_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_open_short_sets_leverage(
        self, executor: OrderExecutor, mock_rest_client: AsyncMock
    ) -> None:
        await executor.execute(
            _make_request(action="OPEN_SHORT", side="sell", pos_side="short")
        )
        mock_rest_client.set_leverage.assert_called_once()

    @pytest.mark.asyncio
    async def test_open_main_order_failure_returns_error(
        self, executor: OrderExecutor, mock_rest_client: AsyncMock
    ) -> None:
        mock_rest_client.place_order.return_value = OrderResult(
            success=False, error_code="51000", error_message="Insufficient balance"
        )
        result = await executor.execute(_make_request())
        assert result.success is False
        assert result.error_code == "51000"
        mock_rest_client.place_algo_order.assert_not_called()


# --- CLOSE flow ---


class TestCloseFlow:
    @pytest.mark.asyncio
    async def test_close_calls_close_position(
        self, executor: OrderExecutor, mock_rest_client: AsyncMock
    ) -> None:
        result = await executor.execute(_make_request(action="CLOSE"))
        assert result.success is True
        mock_rest_client.close_position.assert_called_once_with(
            "BTC-USDT-SWAP", "cross", "long"
        )
        mock_rest_client.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_short_position(
        self, executor: OrderExecutor, mock_rest_client: AsyncMock
    ) -> None:
        await executor.execute(
            _make_request(action="CLOSE", side="buy", pos_side="short")
        )
        mock_rest_client.close_position.assert_called_once_with(
            "BTC-USDT-SWAP", "cross", "short"
        )

    @pytest.mark.asyncio
    async def test_close_api_error(
        self, executor: OrderExecutor, mock_rest_client: AsyncMock
    ) -> None:
        mock_rest_client.close_position.return_value = {
            "code": "1",
            "data": [{"sCode": "51001", "sMsg": "No position"}],
        }
        result = await executor.execute(_make_request(action="CLOSE"))
        assert result.success is False


# --- ADD/REDUCE flow ---


class TestAddReduceFlow:
    @pytest.mark.asyncio
    async def test_add_places_order_only(
        self, executor: OrderExecutor, mock_rest_client: AsyncMock
    ) -> None:
        result = await executor.execute(_make_request(action="ADD"))
        assert result.success is True
        mock_rest_client.place_order.assert_called_once()
        mock_rest_client.set_leverage.assert_not_called()
        mock_rest_client.place_algo_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_reduce_places_order_only(
        self, executor: OrderExecutor, mock_rest_client: AsyncMock
    ) -> None:
        result = await executor.execute(_make_request(action="REDUCE"))
        assert result.success is True
        mock_rest_client.place_order.assert_called_once()
        mock_rest_client.set_leverage.assert_not_called()


# --- Error handling ---


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_exception_during_execution(
        self, executor: OrderExecutor, mock_rest_client: AsyncMock
    ) -> None:
        mock_rest_client.place_order.side_effect = Exception("Connection lost")
        result = await executor.execute(_make_request(action="ADD"))
        assert result.success is False
        assert "Connection lost" in result.error_message

    @pytest.mark.asyncio
    async def test_set_leverage_failure_still_proceeds(
        self, executor: OrderExecutor, mock_rest_client: AsyncMock
    ) -> None:
        mock_rest_client.set_leverage.side_effect = Exception("Leverage error")
        result = await executor.execute(_make_request(action="OPEN_LONG"))
        # Should still attempt to place the order
        assert result.success is True
        mock_rest_client.place_order.assert_called_once()
