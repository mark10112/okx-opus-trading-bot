"""Message formatting (MarkdownV2) for Telegram."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


class MessageFormatter:
    """Format messages for Telegram using Markdown V2."""

    def format_status(
        self,
        equity: float,
        daily_pnl: float,
        positions: list,
        state: str,
        last_decision: dict,
        screener_rate: float,
    ) -> str: ...

    def format_positions(self, positions: list) -> str: ...

    def format_trade_fill(self, fill: dict) -> str: ...

    def format_position_closed(self, position: dict) -> str: ...

    def format_trades_list(self, trades: list) -> str: ...

    def format_performance(self, metrics: dict) -> str: ...

    def format_playbook(self, playbook: dict) -> str: ...

    def format_system_alert(self, alert: dict) -> str: ...

    def format_market_alert(self, alert: dict) -> str: ...

    def format_research_result(self, research: dict) -> str: ...

    def _format_number(self, value: float, decimals: int = 2) -> str:
        """Format number with commas: 102500.00 -> '102,500.00'"""
        ...

    def _format_pct(self, value: float) -> str:
        """Format percentage: 0.012 -> '+1.2%'"""
        ...

    def _format_duration(self, seconds: int) -> str:
        """Format duration: 8100 -> '2h 15m'"""
        ...
