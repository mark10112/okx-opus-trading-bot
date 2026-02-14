"""Read-only query functions for Telegram bot commands."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from ui.db.models import (
    PerformanceSnapshotORM,
    PlaybookVersionORM,
    ScreenerLogORM,
    TradeORM,
)

logger = structlog.get_logger()


class DBQueries:
    """Read-only query functions for Telegram bot commands."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def get_equity_and_pnl(self) -> tuple[float, float]:
        """Query performance_snapshots for latest daily equity + PnL."""
        async with self.session_factory() as session:
            stmt = (
                select(PerformanceSnapshotORM)
                .order_by(PerformanceSnapshotORM.created_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            snap = result.scalars().first()
            if snap is None:
                return 0.0, 0.0
            return float(snap.equity or 0.0), float(snap.total_pnl or 0.0)

    async def get_open_positions(self) -> list[dict]:
        """Query trades WHERE status='open'."""
        async with self.session_factory() as session:
            stmt = select(TradeORM).where(TradeORM.status == "open")
            result = await session.execute(stmt)
            trades = result.scalars().all()
            return [self._trade_to_dict(t) for t in trades]

    async def get_recent_trades(self, limit: int = 10) -> list[dict]:
        """Query trades WHERE status='closed' ORDER BY closed_at DESC LIMIT N."""
        async with self.session_factory() as session:
            stmt = (
                select(TradeORM)
                .where(TradeORM.status == "closed")
                .order_by(TradeORM.closed_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            trades = result.scalars().all()
            return [self._trade_to_dict(t) for t in trades]

    async def get_latest_playbook(self) -> dict:
        """Query playbook_versions ORDER BY version DESC LIMIT 1."""
        async with self.session_factory() as session:
            stmt = (
                select(PlaybookVersionORM)
                .order_by(PlaybookVersionORM.version.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            pb = result.scalars().first()
            if pb is None:
                return {}
            return {
                "version": pb.version,
                "playbook_json": pb.playbook_json,
                "change_summary": pb.change_summary,
                "triggered_by": pb.triggered_by,
                "created_at": pb.created_at,
            }

    async def get_performance_metrics(self, trade_count: int = 100) -> dict:
        """Compute metrics from last N closed trades."""
        async with self.session_factory() as session:
            stmt = (
                select(TradeORM)
                .where(TradeORM.status == "closed")
                .order_by(TradeORM.closed_at.desc())
                .limit(trade_count)
            )
            result = await session.execute(stmt)
            trades = result.scalars().all()

            if not trades:
                return {
                    "total_trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "win_rate": 0.0,
                    "total_pnl": 0.0,
                    "profit_factor": 0.0,
                    "avg_pnl": 0.0,
                }

            total = len(trades)
            wins = sum(1 for t in trades if float(t.pnl_usd or 0) > 0)
            losses = total - wins
            total_pnl = sum(float(t.pnl_usd or 0) for t in trades)
            gross_profit = sum(float(t.pnl_usd) for t in trades if float(t.pnl_usd or 0) > 0)
            gross_loss = abs(
                sum(float(t.pnl_usd) for t in trades if float(t.pnl_usd or 0) <= 0)
            )

            win_rate = wins / total if total > 0 else 0.0
            if gross_loss > 0:
                profit_factor = gross_profit / gross_loss
            elif gross_profit > 0:
                profit_factor = float("inf")
            else:
                profit_factor = 0.0

            return {
                "total_trades": total,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "total_pnl": total_pnl,
                "profit_factor": profit_factor,
                "avg_pnl": total_pnl / total if total > 0 else 0.0,
            }

    async def get_screener_pass_rate(self, hours: int = 24) -> float:
        """Query screener_logs for pass-through rate in last N hours."""
        async with self.session_factory() as session:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            stmt = select(ScreenerLogORM).where(ScreenerLogORM.created_at >= cutoff)
            result = await session.execute(stmt)
            logs = result.scalars().all()

            if not logs:
                return 0.0
            passed = sum(1 for log in logs if log.signal)
            return passed / len(logs)

    async def get_latest_decision(self) -> dict | None:
        """Get most recent Opus decision (most recent trade)."""
        async with self.session_factory() as session:
            stmt = select(TradeORM).order_by(TradeORM.created_at.desc()).limit(1)
            result = await session.execute(stmt)
            trade = result.scalars().first()
            if trade is None:
                return None
            return {
                "trade_id": trade.trade_id,
                "symbol": trade.symbol,
                "direction": trade.direction,
                "strategy": trade.strategy_used,
                "confidence": float(trade.confidence_at_entry or 0),
                "reasoning": trade.opus_reasoning,
                "opened_at": trade.opened_at,
            }

    async def get_daily_trade_summary(self) -> dict:
        """Today's summary: trade count, wins, losses, PnL."""
        async with self.session_factory() as session:
            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            stmt = (
                select(TradeORM)
                .where(TradeORM.status == "closed")
                .where(TradeORM.closed_at >= today_start)
            )
            result = await session.execute(stmt)
            trades = result.scalars().all()

            if not trades:
                return {
                    "trade_count": 0,
                    "wins": 0,
                    "losses": 0,
                    "total_pnl": 0.0,
                }

            wins = sum(1 for t in trades if float(t.pnl_usd or 0) > 0)
            losses = len(trades) - wins
            total_pnl = sum(float(t.pnl_usd or 0) for t in trades)

            return {
                "trade_count": len(trades),
                "wins": wins,
                "losses": losses,
                "total_pnl": total_pnl,
            }

    @staticmethod
    def _trade_to_dict(trade: TradeORM) -> dict:
        """Convert TradeORM row to dict."""
        return {
            "trade_id": trade.trade_id,
            "symbol": trade.symbol,
            "direction": trade.direction,
            "entry_price": float(trade.entry_price),
            "exit_price": float(trade.exit_price) if trade.exit_price else None,
            "stop_loss": float(trade.stop_loss),
            "take_profit": float(trade.take_profit) if trade.take_profit else None,
            "size": float(trade.size),
            "leverage": float(trade.leverage),
            "pnl_usd": float(trade.pnl_usd) if trade.pnl_usd is not None else None,
            "pnl_pct": float(trade.pnl_pct) if trade.pnl_pct is not None else None,
            "fees_usd": float(trade.fees_usd) if trade.fees_usd is not None else None,
            "strategy_used": trade.strategy_used,
            "confidence_at_entry": (
                float(trade.confidence_at_entry) if trade.confidence_at_entry else None
            ),
            "market_regime": trade.market_regime,
            "opus_reasoning": trade.opus_reasoning,
            "exit_reason": trade.exit_reason,
            "status": trade.status,
            "opened_at": trade.opened_at,
            "closed_at": trade.closed_at,
            "duration_seconds": trade.duration_seconds,
        }
