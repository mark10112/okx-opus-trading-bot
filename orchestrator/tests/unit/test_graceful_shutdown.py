"""Tests for graceful shutdown across all main entry points."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestOrchestratorShutdown:
    """Test orchestrator main() graceful shutdown."""

    @pytest.mark.asyncio
    async def test_db_engine_dispose_works(self):
        """AsyncEngine.dispose() can be awaited without error."""
        from orchestrator.db.engine import create_db_engine

        engine = create_db_engine("postgresql+asyncpg://localhost/test")
        # dispose() should work without connecting
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_shutdown_stops_snapshot_scheduler(self):
        """Snapshot scheduler stop() is called on shutdown."""
        from orchestrator.snapshot_scheduler import SnapshotScheduler

        scheduler = SnapshotScheduler(
            trade_repo=AsyncMock(),
            snapshot_repo=AsyncMock(),
        )
        scheduler.start()
        assert scheduler._running is True

        await scheduler.stop()
        assert scheduler._running is False
        assert scheduler._task is None

    @pytest.mark.asyncio
    async def test_shutdown_disconnects_redis(self):
        """Redis disconnect is called on shutdown."""
        from orchestrator.redis_client import RedisClient

        client = RedisClient(redis_url="redis://localhost:6379")
        client.client = AsyncMock()

        await client.disconnect()
        client.client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_orchestrator_stop_sets_running_false(self):
        """Orchestrator.stop() sets running=False."""
        from orchestrator.state_machine import Orchestrator

        settings = MagicMock()
        redis = AsyncMock()
        orch = Orchestrator(settings=settings, redis=redis)
        orch.running = True

        await orch.stop()
        assert orch.running is False


class TestIndicatorTradeShutdown:
    """Test indicator-trade-server shutdown."""

    @pytest.mark.asyncio
    async def test_indicator_server_stop(self):
        """IndicatorServer.stop() sets running=False."""
        from indicator_trade.indicator.server import IndicatorServer

        settings = MagicMock()
        redis = AsyncMock()
        server = IndicatorServer(settings=settings, redis=redis)
        server.running = True

        await server.stop()
        assert server.running is False

    @pytest.mark.asyncio
    async def test_trade_server_stop(self):
        """TradeServer.stop() sets running=False."""
        from indicator_trade.trade.server import TradeServer

        settings = MagicMock()
        redis = AsyncMock()
        server = TradeServer(settings=settings, redis=redis)
        server.running = True

        await server.stop()
        assert server.running is False


class TestUIShutdown:
    """Test UI shutdown with DB engine disposal."""

    @pytest.mark.asyncio
    async def test_db_engine_dispose_works(self):
        """AsyncEngine.dispose() can be awaited without error."""
        from ui.db.engine import create_db_engine

        engine = create_db_engine("postgresql+asyncpg://localhost/test")
        await engine.dispose()


class TestWindowsSignalCompat:
    """Test that main.py files handle Windows signal compatibility."""

    def test_orchestrator_main_has_windows_compat(self):
        """orchestrator main.py should have Windows signal compat."""
        import orchestrator.main as mod
        import inspect

        source = inspect.getsource(mod)
        assert "win32" in source or "add_signal_handler" in source

    def test_indicator_trade_main_has_windows_compat(self):
        """indicator-trade main.py should have Windows signal compat."""
        import indicator_trade.main as mod
        import inspect

        source = inspect.getsource(mod)
        assert "win32" in source or "add_signal_handler" in source

    def test_ui_main_has_windows_compat(self):
        """ui main.py already has Windows signal compat."""
        import ui.main as mod
        import inspect

        source = inspect.getsource(mod)
        assert "win32" in source
