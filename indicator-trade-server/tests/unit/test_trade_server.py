"""Unit tests for trade server main loop."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from indicator_trade.models.messages import TradeOrderMessage
from indicator_trade.models.order import OrderResult
from indicator_trade.models.position import Position
from indicator_trade.trade.server import TradeServer


# --- Fixtures ---


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.OKX_API_KEY = "test-key"
    settings.OKX_SECRET_KEY = "test-secret"
    settings.OKX_PASSPHRASE = "test-pass"
    settings.OKX_FLAG = "1"
    settings.WS_PRIVATE_URL = "wss://wspap.okx.com:8443/ws/v5/private"
    settings.INSTRUMENTS = ["BTC-USDT-SWAP"]
    settings.ORDER_TIMEOUT_SECONDS = 30
    return settings


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.publish = AsyncMock(return_value="msg-id-1")
    redis.subscribe = AsyncMock()
    return redis


@pytest.fixture
def server(mock_settings: MagicMock, mock_redis: AsyncMock) -> TradeServer:
    return TradeServer(settings=mock_settings, redis=mock_redis)


# --- Init ---


class TestInit:
    def test_initial_state(self, server: TradeServer) -> None:
        assert server.running is False
        assert server._rest_client is None
        assert server._ws is None
        assert server._executor is None
        assert server._position_manager is None

    def test_stores_settings(self, server: TradeServer) -> None:
        assert server.settings.OKX_API_KEY == "test-key"


# --- Start / Stop ---


class TestStartStop:
    @pytest.mark.asyncio
    async def test_start_initializes_components(self, server: TradeServer) -> None:
        mock_ws = MagicMock()
        mock_ws.connect = AsyncMock()
        mock_ws.subscribe_orders = AsyncMock()
        mock_ws.subscribe_positions = AsyncMock()
        mock_ws.subscribe_account = AsyncMock()
        mock_ws.disconnect = AsyncMock()

        with patch(
            "indicator_trade.trade.server.OKXRestClient"
        ), patch(
            "indicator_trade.trade.server.OKXPrivateWS", return_value=mock_ws
        ), patch(
            "indicator_trade.trade.server.OrderValidator"
        ), patch(
            "indicator_trade.trade.server.OrderExecutor"
        ), patch(
            "indicator_trade.trade.server.PositionManager"
        ):
            # Make subscribe block briefly then stop
            async def fake_subscribe(streams, callback):
                await asyncio.sleep(0.1)

            server.redis.subscribe = fake_subscribe

            task = asyncio.create_task(server.start())
            await asyncio.sleep(0.2)
            await server.stop()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            assert server._rest_client is not None
            assert server._ws is mock_ws
            mock_ws.connect.assert_called_once()
            mock_ws.subscribe_orders.assert_called_once()
            mock_ws.subscribe_positions.assert_called_once()
            mock_ws.subscribe_account.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self, server: TradeServer) -> None:
        server.running = True
        mock_ws = MagicMock()
        mock_ws.disconnect = AsyncMock()
        server._ws = mock_ws

        await server.stop()

        assert server.running is False
        mock_ws.disconnect.assert_called_once()


# --- _on_trade_order ---


class TestOnTradeOrder:
    @pytest.mark.asyncio
    async def test_on_trade_order_executes_and_publishes_fill(
        self, server: TradeServer, mock_redis: AsyncMock
    ) -> None:
        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(
            return_value=OrderResult(success=True, ord_id="ord-123", fill_price=50000.0)
        )
        server._executor = mock_executor

        order_msg = TradeOrderMessage(
            payload={
                "action": "OPEN_LONG",
                "symbol": "BTC-USDT-SWAP",
                "side": "buy",
                "pos_side": "long",
                "order_type": "market",
                "size": "1",
                "leverage": "3",
            }
        )

        await server._on_trade_order("trade:orders", order_msg)

        mock_executor.execute.assert_called_once()
        # Should publish fill to trade:fills
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == "trade:fills"

    @pytest.mark.asyncio
    async def test_on_trade_order_failed_execution(
        self, server: TradeServer, mock_redis: AsyncMock
    ) -> None:
        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(
            return_value=OrderResult(success=False, error_message="Insufficient balance")
        )
        server._executor = mock_executor

        order_msg = TradeOrderMessage(
            payload={
                "action": "OPEN_LONG",
                "symbol": "BTC-USDT-SWAP",
                "side": "buy",
                "pos_side": "long",
                "order_type": "market",
                "size": "1",
            }
        )

        await server._on_trade_order("trade:orders", order_msg)

        # Should still publish the failed result
        mock_redis.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_trade_order_no_executor(
        self, server: TradeServer, mock_redis: AsyncMock
    ) -> None:
        server._executor = None
        order_msg = TradeOrderMessage(payload={"action": "OPEN_LONG"})

        await server._on_trade_order("trade:orders", order_msg)

        mock_redis.publish.assert_not_called()


# --- _on_order_update ---


class TestOnOrderUpdate:
    @pytest.mark.asyncio
    async def test_on_order_update_logs(self, server: TradeServer) -> None:
        data = {
            "arg": {"channel": "orders"},
            "data": [{"ordId": "123", "state": "filled", "instId": "BTC-USDT-SWAP"}],
        }
        # Should not raise
        await server._on_order_update(data)

    @pytest.mark.asyncio
    async def test_on_order_update_empty_data(self, server: TradeServer) -> None:
        data = {"arg": {"channel": "orders"}, "data": []}
        await server._on_order_update(data)


# --- _on_position_update ---


class TestOnPositionUpdate:
    @pytest.mark.asyncio
    async def test_on_position_update_delegates_to_manager(
        self, server: TradeServer
    ) -> None:
        mock_pm = AsyncMock()
        mock_pm.update = AsyncMock(
            return_value=Position(instId="BTC-USDT-SWAP", posSide="long", pos=1.0)
        )
        server._position_manager = mock_pm

        data = {
            "arg": {"channel": "positions"},
            "data": [
                {
                    "instId": "BTC-USDT-SWAP",
                    "posSide": "long",
                    "pos": "1",
                    "avgPx": "50000",
                }
            ],
        }
        await server._on_position_update(data)

        mock_pm.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_position_update_no_manager(self, server: TradeServer) -> None:
        server._position_manager = None
        data = {"arg": {"channel": "positions"}, "data": [{"pos": "1"}]}
        await server._on_position_update(data)  # Should not raise


# --- _on_account_update ---


class TestOnAccountUpdate:
    @pytest.mark.asyncio
    async def test_on_account_update_stores_state(self, server: TradeServer) -> None:
        data = {
            "arg": {"channel": "account"},
            "data": [
                {
                    "totalEq": "10000",
                    "details": [{"availBal": "8000", "ccy": "USDT"}],
                }
            ],
        }
        await server._on_account_update(data)

        assert server._account_state is not None
        assert server._account_state.equity == 10000.0
        assert server._account_state.available_balance == 8000.0

    @pytest.mark.asyncio
    async def test_on_account_update_empty_data(self, server: TradeServer) -> None:
        data = {"arg": {"channel": "account"}, "data": []}
        await server._on_account_update(data)
        # Should not crash, account_state stays default

    @pytest.mark.asyncio
    async def test_on_account_update_no_usdt(self, server: TradeServer) -> None:
        data = {
            "arg": {"channel": "account"},
            "data": [{"totalEq": "5000", "details": []}],
        }
        await server._on_account_update(data)
        assert server._account_state.equity == 5000.0
        assert server._account_state.available_balance == 0.0
