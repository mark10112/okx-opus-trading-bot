"""Unit tests for OKXPublicWS — OKX Public WebSocket wrapper."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from indicator_trade.indicator.ws_public import OKXPublicWS


@pytest.fixture
def ws() -> OKXPublicWS:
    return OKXPublicWS(url="wss://wspap.okx.com:8443/ws/v5/public")


# --- connect / disconnect ---


class TestConnection:
    async def test_connect_sets_connected(self, ws: OKXPublicWS) -> None:
        with patch.object(ws, "_create_ws_client") as mock_create:
            mock_client = AsyncMock()
            mock_create.return_value = mock_client
            await ws.connect()
            assert ws.connected is True

    async def test_disconnect_sets_not_connected(self, ws: OKXPublicWS) -> None:
        ws.connected = True
        ws._ws = MagicMock()
        await ws.disconnect()
        assert ws.connected is False

    async def test_disconnect_when_not_connected(self, ws: OKXPublicWS) -> None:
        """Should not raise when disconnecting without connection."""
        await ws.disconnect()
        assert ws.connected is False


# --- subscribe_candles ---


class TestSubscribeCandles:
    async def test_subscribe_candles_stores_callback(self, ws: OKXPublicWS) -> None:
        callback = AsyncMock()
        ws._ws = MagicMock()
        ws._ws.subscribe = AsyncMock()
        ws.connected = True

        await ws.subscribe_candles(["BTC-USDT-SWAP"], ["5m", "1H"], callback)

        # Should register callbacks for candle channels
        assert len(ws._callbacks) > 0

    async def test_subscribe_candles_creates_correct_channels(self, ws: OKXPublicWS) -> None:
        callback = AsyncMock()
        ws._ws = MagicMock()
        ws._ws.subscribe = AsyncMock()
        ws.connected = True

        await ws.subscribe_candles(["BTC-USDT-SWAP"], ["5m", "1H", "4H"], callback)

        # Should have channels for each instrument+timeframe combo
        expected_channels = {"candle5m", "candle1H", "candle4H"}
        registered_channels = set(ws._callbacks.keys())
        for ch in expected_channels:
            assert any(ch in k for k in registered_channels)


# --- subscribe_tickers ---


class TestSubscribeTickers:
    async def test_subscribe_tickers_stores_callback(self, ws: OKXPublicWS) -> None:
        callback = AsyncMock()
        ws._ws = MagicMock()
        ws._ws.subscribe = AsyncMock()
        ws.connected = True

        await ws.subscribe_tickers(["BTC-USDT-SWAP"], callback)

        assert len(ws._callbacks) > 0

    async def test_subscribe_tickers_correct_channel(self, ws: OKXPublicWS) -> None:
        callback = AsyncMock()
        ws._ws = MagicMock()
        ws._ws.subscribe = AsyncMock()
        ws.connected = True

        await ws.subscribe_tickers(["BTC-USDT-SWAP"], callback)

        assert any("tickers" in k for k in ws._callbacks.keys())


# --- subscribe_orderbook ---


class TestSubscribeOrderbook:
    async def test_subscribe_orderbook_stores_callback(self, ws: OKXPublicWS) -> None:
        callback = AsyncMock()
        ws._ws = MagicMock()
        ws._ws.subscribe = AsyncMock()
        ws.connected = True

        await ws.subscribe_orderbook(["BTC-USDT-SWAP"], callback)

        assert len(ws._callbacks) > 0


# --- subscribe_funding ---


class TestSubscribeFunding:
    async def test_subscribe_funding_stores_callback(self, ws: OKXPublicWS) -> None:
        callback = AsyncMock()
        ws._ws = MagicMock()
        ws._ws.subscribe = AsyncMock()
        ws.connected = True

        await ws.subscribe_funding(["BTC-USDT-SWAP"], callback)

        assert len(ws._callbacks) > 0


# --- _on_message routing ---


class TestOnMessage:
    async def test_routes_candle_message(self, ws: OKXPublicWS) -> None:
        callback = AsyncMock()
        ws._callbacks["candle1H"] = callback

        message = json.dumps(
            {
                "arg": {"channel": "candle1H", "instId": "BTC-USDT-SWAP"},
                "data": [["1234567890000", "100", "105", "95", "102", "1000"]],
            }
        )
        await ws._on_message(message)

        callback.assert_awaited_once()

    async def test_routes_ticker_message(self, ws: OKXPublicWS) -> None:
        callback = AsyncMock()
        ws._callbacks["tickers"] = callback

        message = json.dumps(
            {
                "arg": {"channel": "tickers", "instId": "BTC-USDT-SWAP"},
                "data": [{"last": "100.0", "askPx": "100.1", "bidPx": "99.9"}],
            }
        )
        await ws._on_message(message)

        callback.assert_awaited_once()

    async def test_ignores_unknown_channel(self, ws: OKXPublicWS) -> None:
        """Should not raise on unknown channel."""
        message = json.dumps(
            {
                "arg": {"channel": "unknown_channel", "instId": "BTC-USDT-SWAP"},
                "data": [],
            }
        )
        await ws._on_message(message)  # Should not raise

    async def test_ignores_non_data_messages(self, ws: OKXPublicWS) -> None:
        """Subscription confirmations and pongs should be ignored."""
        message = json.dumps({"event": "subscribe", "arg": {"channel": "tickers"}})
        await ws._on_message(message)  # Should not raise

    async def test_handles_malformed_json(self, ws: OKXPublicWS) -> None:
        """Should not raise on malformed JSON."""
        await ws._on_message("not valid json {{{")  # Should not raise


# --- _reconnect ---


class TestReconnect:
    async def test_reconnect_with_backoff(self, ws: OKXPublicWS) -> None:
        ws._reconnect_attempts = 0
        ws._max_reconnect_delay = 2

        with patch.object(ws, "connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = [ConnectionError("fail"), None]
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await ws._reconnect()

                # Should have attempted reconnect
                assert mock_connect.await_count >= 1

    async def test_reconnect_resets_attempts_on_success(self, ws: OKXPublicWS) -> None:
        ws._reconnect_attempts = 3

        with patch.object(ws, "connect", new_callable=AsyncMock):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await ws._reconnect()

                assert ws._reconnect_attempts == 0
