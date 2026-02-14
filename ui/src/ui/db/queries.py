"""Read-only query functions for Telegram bot commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()


class DBQueries:
    """Read-only query functions for Telegram bot commands."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def get_equity_and_pnl(self) -> tuple[float, float]:
        """Query performance_snapshots for latest daily equity + PnL."""
        ...

    async def get_open_positions(self) -> list[dict]:
        """Query trades WHERE status='open'."""
        ...

    async def get_recent_trades(self, limit: int = 10) -> list[dict]:
        """Query trades WHERE status='closed' ORDER BY closed_at DESC LIMIT N."""
        ...

    async def get_latest_playbook(self) -> dict:
        """Query playbook_versions ORDER BY version DESC LIMIT 1."""
        ...

    async def get_performance_metrics(self, trade_count: int = 100) -> dict:
        """Compute metrics from last N closed trades."""
        ...

    async def get_screener_pass_rate(self, hours: int = 24) -> float:
        """Query screener_logs for pass-through rate in last N hours."""
        ...

    async def get_latest_decision(self) -> dict | None:
        """Get most recent Opus decision."""
        ...

    async def get_daily_trade_summary(self) -> dict:
        """Today's summary: trade count, wins, losses, PnL."""
        ...
