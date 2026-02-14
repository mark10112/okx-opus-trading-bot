"""Periodic performance snapshot scheduler (hourly/daily/weekly)."""

from __future__ import annotations

import asyncio
import math
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from orchestrator.db.repository import PerformanceSnapshotRepository, TradeRepository

logger = structlog.get_logger()

TICK_INTERVAL_SECONDS = 60  # Check every minute


class SnapshotScheduler:
    """Background task that saves performance snapshots on schedule."""

    def __init__(
        self,
        trade_repo: TradeRepository,
        snapshot_repo: PerformanceSnapshotRepository,
    ) -> None:
        self.trade_repo = trade_repo
        self.snapshot_repo = snapshot_repo
        self._task: asyncio.Task | None = None
        self._running = False

    def start(self) -> None:
        """Start the scheduler background task."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("snapshot_scheduler_started")

    async def stop(self) -> None:
        """Stop the scheduler and cancel the background task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("snapshot_scheduler_stopped")

    async def _run_loop(self) -> None:
        """Main loop: check every minute if a snapshot is due."""
        while self._running:
            try:
                now = datetime.now(timezone.utc)

                if self._should_take_hourly(now):
                    await self._take_snapshot("hourly")

                if self._should_take_daily(now):
                    await self._take_snapshot("daily")

                if self._should_take_weekly(now):
                    await self._take_snapshot("weekly")

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("snapshot_scheduler_error")

            await asyncio.sleep(TICK_INTERVAL_SECONDS)

    async def _take_snapshot(self, snapshot_type: str) -> None:
        """Compute metrics and save a snapshot."""
        metrics = await self._compute_metrics()
        await self.snapshot_repo.save(snapshot_type, metrics)
        logger.info("snapshot_taken", type=snapshot_type, trades=metrics["total_trades"])

    async def _compute_metrics(self) -> dict:
        """Calculate performance metrics from recent closed trades."""
        trades = await self.trade_repo.get_recent_closed(limit=1000)

        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "sharpe_ratio": 0.0,
                "total_pnl": 0.0,
                "max_drawdown": 0.0,
            }

        total = len(trades)
        pnls = [t.pnl_usd or 0.0 for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        win_rate = len(wins) / total if total > 0 else 0.0
        total_pnl = sum(pnls)

        sum_wins = sum(wins)
        sum_losses = abs(sum(losses))
        if sum_losses > 0:
            profit_factor = sum_wins / sum_losses
        elif sum_wins > 0:
            profit_factor = float("inf")
        else:
            profit_factor = 0.0

        # Sharpe ratio (simplified: mean/std of PnL)
        if len(pnls) > 1:
            mean_pnl = total_pnl / total
            variance = sum((p - mean_pnl) ** 2 for p in pnls) / (total - 1)
            std_pnl = math.sqrt(variance) if variance > 0 else 0.0
            sharpe = mean_pnl / std_pnl if std_pnl > 0 else 0.0
        else:
            sharpe = 0.0

        # Max drawdown
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for p in pnls:
            cumulative += p
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd

        return {
            "total_trades": total,
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 4) if profit_factor != float("inf") else float("inf"),
            "sharpe_ratio": round(sharpe, 4),
            "total_pnl": round(total_pnl, 4),
            "max_drawdown": round(max_dd, 4),
        }

    @staticmethod
    def _should_take_hourly(now: datetime) -> bool:
        """True at the start of every hour (minute == 0)."""
        return now.minute == 0

    @staticmethod
    def _should_take_daily(now: datetime) -> bool:
        """True at midnight UTC (hour == 0, minute == 0)."""
        return now.hour == 0 and now.minute == 0

    @staticmethod
    def _should_take_weekly(now: datetime) -> bool:
        """True on Sunday midnight UTC (weekday 6, hour 0, minute 0)."""
        return now.weekday() == 6 and now.hour == 0 and now.minute == 0
