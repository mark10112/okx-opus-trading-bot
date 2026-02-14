"""Tests for SnapshotScheduler — periodic performance snapshots."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_trade(pnl: float, strategy: str = "momentum", regime: str = "trending_up") -> dict:
    return {
        "trade_id": "t1",
        "pnl_usd": pnl,
        "strategy_used": strategy,
        "market_regime": regime,
    }


class TestSnapshotScheduler:
    """Test SnapshotScheduler timing and metric computation."""

    def _make_scheduler(self, trade_repo=None, snapshot_repo=None):
        from orchestrator.snapshot_scheduler import SnapshotScheduler

        return SnapshotScheduler(
            trade_repo=trade_repo or AsyncMock(),
            snapshot_repo=snapshot_repo or AsyncMock(),
        )

    def test_init(self):
        """SnapshotScheduler initializes with repos and task=None."""
        scheduler = self._make_scheduler()
        assert scheduler._task is None
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_compute_metrics_no_trades(self):
        """compute_metrics returns zeros when no trades."""
        trade_repo = AsyncMock()
        trade_repo.get_recent_closed.return_value = []
        scheduler = self._make_scheduler(trade_repo=trade_repo)

        metrics = await scheduler._compute_metrics()
        assert metrics["total_trades"] == 0
        assert metrics["win_rate"] == 0.0
        assert metrics["total_pnl"] == 0.0

    @pytest.mark.asyncio
    async def test_compute_metrics_with_trades(self):
        """compute_metrics calculates win_rate, profit_factor, total_pnl."""
        trade_repo = AsyncMock()
        trades = [
            MagicMock(pnl_usd=100.0, pnl_pct=0.01),
            MagicMock(pnl_usd=-50.0, pnl_pct=-0.005),
            MagicMock(pnl_usd=200.0, pnl_pct=0.02),
        ]
        trade_repo.get_recent_closed.return_value = trades
        scheduler = self._make_scheduler(trade_repo=trade_repo)

        metrics = await scheduler._compute_metrics()
        assert metrics["total_trades"] == 3
        assert abs(metrics["win_rate"] - 2 / 3) < 0.001
        assert metrics["total_pnl"] == 250.0
        assert metrics["profit_factor"] == 300.0 / 50.0  # 6.0

    @pytest.mark.asyncio
    async def test_take_snapshot_saves_to_repo(self):
        """_take_snapshot computes metrics and saves via snapshot_repo."""
        trade_repo = AsyncMock()
        trade_repo.get_recent_closed.return_value = [
            MagicMock(pnl_usd=100.0, pnl_pct=0.01),
        ]
        snapshot_repo = AsyncMock()
        snapshot_repo.save.return_value = 1
        scheduler = self._make_scheduler(trade_repo=trade_repo, snapshot_repo=snapshot_repo)

        await scheduler._take_snapshot("hourly")
        snapshot_repo.save.assert_called_once()
        call_args = snapshot_repo.save.call_args
        assert call_args[0][0] == "hourly"
        data = call_args[0][1]
        assert data["total_trades"] == 1
        assert data["win_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_take_snapshot_daily(self):
        """_take_snapshot works with 'daily' type."""
        snapshot_repo = AsyncMock()
        snapshot_repo.save.return_value = 1
        trade_repo = AsyncMock()
        trade_repo.get_recent_closed.return_value = []
        scheduler = self._make_scheduler(trade_repo=trade_repo, snapshot_repo=snapshot_repo)

        await scheduler._take_snapshot("daily")
        snapshot_repo.save.assert_called_once()
        assert snapshot_repo.save.call_args[0][0] == "daily"

    @pytest.mark.asyncio
    async def test_take_snapshot_weekly(self):
        """_take_snapshot works with 'weekly' type."""
        snapshot_repo = AsyncMock()
        snapshot_repo.save.return_value = 1
        trade_repo = AsyncMock()
        trade_repo.get_recent_closed.return_value = []
        scheduler = self._make_scheduler(trade_repo=trade_repo, snapshot_repo=snapshot_repo)

        await scheduler._take_snapshot("weekly")
        snapshot_repo.save.assert_called_once()
        assert snapshot_repo.save.call_args[0][0] == "weekly"

    @pytest.mark.asyncio
    async def test_start_creates_task(self):
        """start() creates a background asyncio task."""
        scheduler = self._make_scheduler()
        scheduler.start()
        assert scheduler._running is True
        assert scheduler._task is not None
        # Cleanup
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        """stop() cancels the background task."""
        scheduler = self._make_scheduler()
        scheduler.start()
        assert scheduler._running is True
        await scheduler.stop()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_should_take_hourly(self):
        """_should_take returns True for hourly at minute 0."""
        scheduler = self._make_scheduler()
        dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert scheduler._should_take_hourly(dt) is True

    @pytest.mark.asyncio
    async def test_should_not_take_hourly(self):
        """_should_take returns False for hourly at minute != 0."""
        scheduler = self._make_scheduler()
        dt = datetime(2026, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
        assert scheduler._should_take_hourly(dt) is False

    @pytest.mark.asyncio
    async def test_should_take_daily(self):
        """_should_take_daily returns True at midnight UTC."""
        scheduler = self._make_scheduler()
        dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert scheduler._should_take_daily(dt) is True

    @pytest.mark.asyncio
    async def test_should_not_take_daily(self):
        """_should_take_daily returns False at non-midnight."""
        scheduler = self._make_scheduler()
        dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert scheduler._should_take_daily(dt) is False

    @pytest.mark.asyncio
    async def test_should_take_weekly(self):
        """_should_take_weekly returns True on Sunday midnight UTC."""
        scheduler = self._make_scheduler()
        # 2026-01-04 is a Sunday
        dt = datetime(2026, 1, 4, 0, 0, 0, tzinfo=timezone.utc)
        assert scheduler._should_take_weekly(dt) is True

    @pytest.mark.asyncio
    async def test_should_not_take_weekly(self):
        """_should_take_weekly returns False on non-Sunday."""
        scheduler = self._make_scheduler()
        # 2026-01-05 is a Monday
        dt = datetime(2026, 1, 5, 0, 0, 0, tzinfo=timezone.utc)
        assert scheduler._should_take_weekly(dt) is False

    @pytest.mark.asyncio
    async def test_compute_metrics_profit_factor_all_wins(self):
        """profit_factor is inf when all trades are wins."""
        trade_repo = AsyncMock()
        trades = [MagicMock(pnl_usd=100.0, pnl_pct=0.01)]
        trade_repo.get_recent_closed.return_value = trades
        scheduler = self._make_scheduler(trade_repo=trade_repo)

        metrics = await scheduler._compute_metrics()
        assert metrics["profit_factor"] == float("inf")

    @pytest.mark.asyncio
    async def test_compute_metrics_profit_factor_all_losses(self):
        """profit_factor is 0 when all trades are losses."""
        trade_repo = AsyncMock()
        trades = [MagicMock(pnl_usd=-50.0, pnl_pct=-0.005)]
        trade_repo.get_recent_closed.return_value = trades
        scheduler = self._make_scheduler(trade_repo=trade_repo)

        metrics = await scheduler._compute_metrics()
        assert metrics["profit_factor"] == 0.0
