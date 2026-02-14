"""Unit tests for IndicatorServer — main loop orchestration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from indicator_trade.config import Settings
from indicator_trade.indicator.server import IndicatorServer
from indicator_trade.models.candle import Candle


def _make_settings(**overrides) -> Settings:
    defaults = {
        "OKX_API_KEY": "test-key",
        "OKX_SECRET_KEY": "test-secret",
        "OKX_PASSPHRASE": "test-pass",
        "OKX_FLAG": "1",
        "INSTRUMENTS": ["BTC-USDT-SWAP"],
        "TIMEFRAMES": ["5m", "1H", "4H"],
        "CANDLE_HISTORY_LIMIT": 200,
        "SNAPSHOT_INTERVAL_SECONDS": 300,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_candle(close: float = 100.0) -> Candle:
    return Candle(
        time=datetime.now(timezone.utc),
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        open=Decimal("99.0"),
        high=Decimal("105.0"),
        low=Decimal("95.0"),
        close=Decimal(str(close)),
        volume=Decimal("1000.0"),
    )


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.publish = AsyncMock(return_value="msg-id-1")
    return redis


@pytest.fixture
def settings() -> Settings:
    return _make_settings()


@pytest.fixture
def server(settings: Settings, mock_redis: AsyncMock) -> IndicatorServer:
    return IndicatorServer(settings=settings, redis=mock_redis)


# --- Initialization ---


class TestInit:
    def test_server_created(self, server: IndicatorServer) -> None:
        assert server.running is False

    def test_server_has_settings(self, server: IndicatorServer, settings: Settings) -> None:
        assert server.settings is settings

    def test_server_has_redis(self, server: IndicatorServer, mock_redis: AsyncMock) -> None:
        assert server.redis is mock_redis


# --- start() orchestration ---


class TestStart:
    async def test_start_sets_running(self, server: IndicatorServer) -> None:
        """start() should set running=True and call backfill + subscribe + snapshot loop."""
        with (
            patch.object(server, "_backfill_candles", new_callable=AsyncMock),
            patch.object(server, "_subscribe_ws", new_callable=AsyncMock),
            patch.object(server, "_snapshot_loop", new_callable=AsyncMock) as mock_loop,
        ):
            # Make snapshot_loop stop after first check
            mock_loop.side_effect = asyncio.CancelledError()
            try:
                await server.start()
            except asyncio.CancelledError:
                pass

            assert server.running is True

    async def test_start_calls_backfill(self, server: IndicatorServer) -> None:
        with (
            patch.object(server, "_backfill_candles", new_callable=AsyncMock) as mock_backfill,
            patch.object(server, "_subscribe_ws", new_callable=AsyncMock),
            patch.object(server, "_snapshot_loop", new_callable=AsyncMock) as mock_loop,
        ):
            mock_loop.side_effect = asyncio.CancelledError()
            try:
                await server.start()
            except asyncio.CancelledError:
                pass

            mock_backfill.assert_awaited_once()

    async def test_start_calls_subscribe_ws(self, server: IndicatorServer) -> None:
        with (
            patch.object(server, "_backfill_candles", new_callable=AsyncMock),
            patch.object(server, "_subscribe_ws", new_callable=AsyncMock) as mock_subscribe,
            patch.object(server, "_snapshot_loop", new_callable=AsyncMock) as mock_loop,
        ):
            mock_loop.side_effect = asyncio.CancelledError()
            try:
                await server.start()
            except asyncio.CancelledError:
                pass

            mock_subscribe.assert_awaited_once()

    async def test_start_calls_snapshot_loop(self, server: IndicatorServer) -> None:
        with (
            patch.object(server, "_backfill_candles", new_callable=AsyncMock),
            patch.object(server, "_subscribe_ws", new_callable=AsyncMock),
            patch.object(server, "_snapshot_loop", new_callable=AsyncMock) as mock_loop,
        ):
            mock_loop.side_effect = asyncio.CancelledError()
            try:
                await server.start()
            except asyncio.CancelledError:
                pass

            mock_loop.assert_awaited_once()


# --- stop() ---


class TestStop:
    async def test_stop_sets_not_running(self, server: IndicatorServer) -> None:
        server.running = True
        await server.stop()
        assert server.running is False


# --- _backfill_candles ---


class TestBackfill:
    async def test_backfill_calls_rest_api(self, server: IndicatorServer) -> None:
        """Should fetch candles from OKX REST for each instrument+timeframe."""
        mock_candle_store = AsyncMock()
        server._candle_store = mock_candle_store

        with patch.object(server, "_fetch_candles_rest", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [_make_candle(close=float(100 + i)) for i in range(5)]
            await server._backfill_candles()

            # Should be called for each instrument x timeframe
            assert mock_fetch.await_count == len(server.settings.INSTRUMENTS) * len(
                server.settings.TIMEFRAMES
            )

    async def test_backfill_stores_candles(self, server: IndicatorServer) -> None:
        mock_candle_store = AsyncMock()
        server._candle_store = mock_candle_store
        candles = [_make_candle(close=float(100 + i)) for i in range(5)]

        with patch.object(server, "_fetch_candles_rest", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = candles
            await server._backfill_candles()

            # backfill should be called on candle_store
            assert mock_candle_store.backfill.await_count > 0


# --- _snapshot_loop ---


class TestSnapshotLoop:
    async def test_snapshot_loop_publishes(
        self, server: IndicatorServer, mock_redis: AsyncMock
    ) -> None:
        """Snapshot loop should build snapshot and publish to Redis."""
        server.running = True

        mock_snapshot_builder = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.model_dump.return_value = {"ticker": {"symbol": "BTC-USDT-SWAP"}}
        mock_snapshot_builder.build.return_value = mock_snapshot
        server._snapshot_builder = mock_snapshot_builder

        # Mock REST data fetchers
        with (
            patch.object(server, "_fetch_ticker", new_callable=AsyncMock) as mock_ticker,
            patch.object(server, "_fetch_orderbook", new_callable=AsyncMock) as mock_ob,
            patch.object(server, "_fetch_funding", new_callable=AsyncMock) as mock_fund,
            patch.object(server, "_fetch_open_interest", new_callable=AsyncMock) as mock_oi,
            patch.object(server, "_detect_anomalies", new_callable=AsyncMock),
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            from indicator_trade.models.ticker import Ticker
            from indicator_trade.models.snapshot import OrderBook, FundingRate, OpenInterest

            mock_ticker.return_value = Ticker(
                symbol="BTC-USDT-SWAP",
                last=100.0,
                bid=99.9,
                ask=100.1,
                volume_24h=50000.0,
                change_24h=1.5,
            )
            mock_ob.return_value = OrderBook()
            mock_fund.return_value = FundingRate()
            mock_oi.return_value = OpenInterest()

            # Stop after one iteration
            call_count = 0

            async def stop_after_one(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count >= 1:
                    server.running = False

            mock_sleep.side_effect = stop_after_one

            await server._snapshot_loop()

            # Should have published at least once
            assert mock_redis.publish.await_count >= 1


# --- _detect_anomalies ---


class TestDetectAnomalies:
    async def test_detects_large_price_change(
        self, server: IndicatorServer, mock_redis: AsyncMock
    ) -> None:
        """Price change > 3% in 1H should trigger market alert."""
        mock_snapshot = MagicMock()
        mock_snapshot.price_change_1h = 4.0  # > 3%
        mock_snapshot.funding_rate = MagicMock()
        mock_snapshot.funding_rate.current = 0.01  # normal

        await server._detect_anomalies(mock_snapshot)

        # Should publish alert
        mock_redis.publish.assert_awaited()

    async def test_no_anomaly_for_small_change(
        self, server: IndicatorServer, mock_redis: AsyncMock
    ) -> None:
        """Price change < 3% should not trigger alert."""
        mock_snapshot = MagicMock()
        mock_snapshot.price_change_1h = 1.0  # < 3%
        mock_snapshot.funding_rate = MagicMock()
        mock_snapshot.funding_rate.current = 0.01  # < 0.05%

        await server._detect_anomalies(mock_snapshot)

        mock_redis.publish.assert_not_awaited()

    async def test_detects_funding_spike(
        self, server: IndicatorServer, mock_redis: AsyncMock
    ) -> None:
        """Funding rate > 0.05% should trigger alert."""
        mock_snapshot = MagicMock()
        mock_snapshot.price_change_1h = 0.5  # normal
        mock_snapshot.funding_rate = MagicMock()
        mock_snapshot.funding_rate.current = 0.06  # > 0.05%

        await server._detect_anomalies(mock_snapshot)

        mock_redis.publish.assert_awaited()
