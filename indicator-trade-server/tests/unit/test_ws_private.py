"""Unit tests for OKX Private WebSocket wrapper."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from indicator_trade.trade.ws_private import OKXPrivateWS


# --- Fixtures ---


@pytest.fixture
def ws() -> OKXPrivateWS:
    return OKXPrivateWS(
        url="wss://wspap.okx.com:8443/ws/v5/private",
        api_key="test-key",
        passphrase="test-pass",
        secret_key="test-secret",
    )


# --- Constructor ---


class TestInit:
    def test_stores_credentials(self, ws: OKXPrivateWS) -> None:
        assert ws.url == "wss://wspap.okx.com:8443/ws/v5/private"
        assert ws.api_key == "test-key"
        assert ws.passphrase == "test-pass"
        assert ws.secret_key == "test-secret"

    def test_initial_state(self, ws: OKXPrivateWS) -> None:
        assert ws.connected is False
        assert ws._callbacks == {}
        assert ws._subscriptions == []


# --- Connect / Disconnect ---


def _make_mock_ws_client():
    """Create a mock WS client matching the new connect flow."""
    mock = MagicMock()
    mock.connect = AsyncMock()
    mock.login = AsyncMock(return_value=True)
    mock.consume = AsyncMock()
    mock.stop = AsyncMock()
    mock.websocket = MagicMock()
    mock.websocket.send = AsyncMock()
    mock.loop = MagicMock()
    mock.loop.create_task = MagicMock()
    return mock


class TestConnect:
    @pytest.mark.asyncio
    async def test_connect_creates_ws_and_authenticates(self, ws: OKXPrivateWS) -> None:
        mock_ws_client = _make_mock_ws_client()
        ws._create_ws_client = MagicMock(return_value=mock_ws_client)

        with patch("indicator_trade.trade.ws_private.asyncio.sleep", new_callable=AsyncMock):
            await ws.connect()

        ws._create_ws_client.assert_called_once()
        mock_ws_client.connect.assert_called_once()
        mock_ws_client.login.assert_called_once()
        mock_ws_client.loop.create_task.assert_called_once()
        assert ws.connected is True

    @pytest.mark.asyncio
    async def test_disconnect_stops_ws(self, ws: OKXPrivateWS) -> None:
        mock_ws_client = _make_mock_ws_client()
        ws._create_ws_client = MagicMock(return_value=mock_ws_client)

        with patch("indicator_trade.trade.ws_private.asyncio.sleep", new_callable=AsyncMock):
            await ws.connect()
        await ws.disconnect()

        mock_ws_client.stop.assert_called_once()
        assert ws.connected is False
        assert ws._ws is None

    @pytest.mark.asyncio
    async def test_disconnect_handles_stop_error(self, ws: OKXPrivateWS) -> None:
        mock_ws_client = _make_mock_ws_client()
        mock_ws_client.stop = AsyncMock(side_effect=Exception("stop error"))
        ws._create_ws_client = MagicMock(return_value=mock_ws_client)

        with patch("indicator_trade.trade.ws_private.asyncio.sleep", new_callable=AsyncMock):
            await ws.connect()
        await ws.disconnect()  # Should not raise

        assert ws.connected is False


# --- Subscribe ---


class TestSubscribeOrders:
    @pytest.mark.asyncio
    async def test_subscribe_orders_registers_callback(self, ws: OKXPrivateWS) -> None:
        mock_ws_client = _make_mock_ws_client()
        ws._create_ws_client = MagicMock(return_value=mock_ws_client)
        with patch("indicator_trade.trade.ws_private.asyncio.sleep", new_callable=AsyncMock):
            await ws.connect()

        callback = AsyncMock()
        await ws.subscribe_orders("SWAP", callback)

        assert "orders" in ws._callbacks
        assert ws._callbacks["orders"] is callback
        assert len(ws._subscriptions) == 1
        assert ws._subscriptions[0] == {"channel": "orders", "instType": "SWAP"}

    @pytest.mark.asyncio
    async def test_subscribe_orders_sends_payload(self, ws: OKXPrivateWS) -> None:
        mock_ws_client = _make_mock_ws_client()
        ws._create_ws_client = MagicMock(return_value=mock_ws_client)
        with patch("indicator_trade.trade.ws_private.asyncio.sleep", new_callable=AsyncMock):
            await ws.connect()

        callback = AsyncMock()
        await ws.subscribe_orders("SWAP", callback)

        mock_ws_client.websocket.send.assert_called_once()


class TestSubscribePositions:
    @pytest.mark.asyncio
    async def test_subscribe_positions_registers_callback(self, ws: OKXPrivateWS) -> None:
        mock_ws_client = _make_mock_ws_client()
        ws._create_ws_client = MagicMock(return_value=mock_ws_client)
        with patch("indicator_trade.trade.ws_private.asyncio.sleep", new_callable=AsyncMock):
            await ws.connect()

        callback = AsyncMock()
        await ws.subscribe_positions("SWAP", callback)

        assert "positions" in ws._callbacks
        assert ws._subscriptions[0] == {"channel": "positions", "instType": "SWAP"}


class TestSubscribeAccount:
    @pytest.mark.asyncio
    async def test_subscribe_account_registers_callback(self, ws: OKXPrivateWS) -> None:
        mock_ws_client = _make_mock_ws_client()
        ws._create_ws_client = MagicMock(return_value=mock_ws_client)
        with patch("indicator_trade.trade.ws_private.asyncio.sleep", new_callable=AsyncMock):
            await ws.connect()

        callback = AsyncMock()
        await ws.subscribe_account(callback)

        assert "account" in ws._callbacks
        assert ws._subscriptions[0] == {"channel": "account"}


# --- Message routing ---


class TestMessageRouting:
    @pytest.mark.asyncio
    async def test_on_message_routes_orders(self, ws: OKXPrivateWS) -> None:
        callback = AsyncMock()
        ws._callbacks["orders"] = callback

        message = json.dumps(
            {
                "arg": {"channel": "orders", "instType": "SWAP"},
                "data": [{"ordId": "123", "state": "filled"}],
            }
        )
        await ws._on_message(message)

        callback.assert_called_once()
        call_data = callback.call_args[0][0]
        assert call_data["arg"]["channel"] == "orders"

    @pytest.mark.asyncio
    async def test_on_message_routes_positions(self, ws: OKXPrivateWS) -> None:
        callback = AsyncMock()
        ws._callbacks["positions"] = callback

        message = json.dumps(
            {
                "arg": {"channel": "positions", "instType": "SWAP"},
                "data": [{"instId": "BTC-USDT-SWAP", "pos": "1"}],
            }
        )
        await ws._on_message(message)

        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_routes_account(self, ws: OKXPrivateWS) -> None:
        callback = AsyncMock()
        ws._callbacks["account"] = callback

        message = json.dumps(
            {
                "arg": {"channel": "account"},
                "data": [{"totalEq": "10000"}],
            }
        )
        await ws._on_message(message)

        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_ignores_subscribe_confirmation(self, ws: OKXPrivateWS) -> None:
        callback = AsyncMock()
        ws._callbacks["orders"] = callback

        # Subscribe confirmation has "event" but no "data"
        message = json.dumps({"event": "subscribe", "arg": {"channel": "orders"}})
        await ws._on_message(message)

        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_ignores_invalid_json(self, ws: OKXPrivateWS) -> None:
        callback = AsyncMock()
        ws._callbacks["orders"] = callback

        await ws._on_message("not json")

        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_unhandled_channel(self, ws: OKXPrivateWS) -> None:
        # No callback registered for "unknown"
        message = json.dumps(
            {
                "arg": {"channel": "unknown"},
                "data": [{}],
            }
        )
        await ws._on_message(message)  # Should not raise

    @pytest.mark.asyncio
    async def test_on_message_callback_exception_handled(self, ws: OKXPrivateWS) -> None:
        callback = AsyncMock(side_effect=Exception("callback error"))
        ws._callbacks["orders"] = callback

        message = json.dumps(
            {
                "arg": {"channel": "orders", "instType": "SWAP"},
                "data": [{"ordId": "123"}],
            }
        )
        await ws._on_message(message)  # Should not raise


# --- Reconnect ---


class TestReconnect:
    @pytest.mark.asyncio
    async def test_reconnect_exponential_backoff(self, ws: OKXPrivateWS) -> None:
        ws._reconnect_attempts = 0
        assert ws._get_reconnect_delay() == 1  # 2^0
        ws._reconnect_attempts = 3
        assert ws._get_reconnect_delay() == 8  # 2^3
        ws._reconnect_attempts = 10
        assert ws._get_reconnect_delay() == 60  # capped at max

    @pytest.mark.asyncio
    async def test_reconnect_resubscribes(self, ws: OKXPrivateWS) -> None:
        mock_ws_client = _make_mock_ws_client()
        ws._create_ws_client = MagicMock(return_value=mock_ws_client)

        ws._subscriptions = [
            {"channel": "orders", "instType": "SWAP"},
            {"channel": "positions", "instType": "SWAP"},
        ]

        # Patch sleep to avoid waiting
        with patch("indicator_trade.trade.ws_private.asyncio.sleep", new_callable=AsyncMock):
            await ws._reconnect()

        # Should have re-subscribed both channels via websocket.send
        assert mock_ws_client.websocket.send.call_count == 2
        assert ws._reconnect_attempts == 0
