"""Message formatting (plain text) for Telegram."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


class MessageFormatter:
    """Format messages for Telegram using plain text."""

    def format_status(
        self,
        equity: float,
        daily_pnl: float,
        positions: list,
        state: str,
        last_decision: dict | None,
        screener_rate: float,
    ) -> str:
        pnl_sign = "+" if daily_pnl >= 0 else ""
        lines = [
            "📊 Bot Status",
            f"State: {state}",
            f"Equity: ${self._format_number(equity)}",
            f"Daily PnL: {pnl_sign}${self._format_number(abs(daily_pnl))}",
            f"Open Positions: {len(positions)}",
            f"Screener Pass Rate: {screener_rate * 100:.0f}%",
        ]
        if last_decision:
            lines.append(
                f"Last Decision: {last_decision.get('strategy', 'N/A')} "
                f"(conf: {last_decision.get('confidence', 0):.0%})"
            )
        return "\n".join(lines)

    def format_positions(self, positions: list) -> str:
        if not positions:
            return "📭 No open positions"
        lines = ["📈 Open Positions"]
        for p in positions:
            pnl = p.get("pnl_usd")
            pnl_str = f"${self._format_number(pnl)}" if pnl is not None else "N/A"
            lines.append(
                f"\n{p['symbol']} {p['direction']}\n"
                f"  Entry: ${self._format_number(p['entry_price'])}\n"
                f"  Size: {p['size']} | Lev: {p['leverage']}x\n"
                f"  PnL: {pnl_str}\n"
                f"  SL: ${self._format_number(p['stop_loss'])} | "
                f"TP: ${self._format_number(p.get('take_profit', 0))}"
            )
        return "\n".join(lines)

    def format_trade_fill(self, fill: dict) -> str:
        action = fill.get("action", "TRADE")
        symbol = fill.get("symbol", "N/A")
        direction = fill.get("direction", "")
        lines = [f"🔔 Trade Fill: {action}"]
        lines.append(f"Symbol: {symbol} {direction}")
        if "entry_price" in fill:
            lines.append(f"Entry: ${self._format_number(fill['entry_price'])}")
        if "exit_price" in fill:
            lines.append(f"Exit: ${self._format_number(fill['exit_price'])}")
        if "size" in fill:
            lines.append(f"Size: {fill['size']}")
        if "leverage" in fill:
            lines.append(f"Leverage: {fill['leverage']}x")
        if "pnl_usd" in fill:
            lines.append(f"PnL: ${self._format_number(fill['pnl_usd'])}")
        if "strategy" in fill:
            lines.append(f"Strategy: {fill['strategy']}")
        return "\n".join(lines)

    def format_position_closed(self, position: dict) -> str:
        pnl = position.get("pnl_usd", 0)
        emoji = "✅" if pnl >= 0 else "❌"
        duration = position.get("duration_seconds", 0)
        lines = [
            f"{emoji} Position Closed",
            f"Symbol: {position.get('symbol', 'N/A')} {position.get('direction', '')}",
            f"Entry: ${self._format_number(position.get('entry_price', 0))}",
            f"Exit: ${self._format_number(position.get('exit_price', 0))}",
            f"PnL: ${self._format_number(pnl)} ({self._format_pct(position.get('pnl_pct', 0))})",
            f"Duration: {self._format_duration(duration)}",
            f"Strategy: {position.get('strategy_used', 'N/A')}",
            f"Exit Reason: {position.get('exit_reason', 'N/A')}",
        ]
        return "\n".join(lines)

    def format_trades_list(self, trades: list) -> str:
        if not trades:
            return "📭 No recent trades"
        lines = [f"📋 Recent Trades ({len(trades)})"]
        for t in trades:
            pnl = t.get("pnl_usd", 0)
            emoji = "✅" if pnl and pnl >= 0 else "❌"
            lines.append(
                f"\n{emoji} {t.get('symbol', 'N/A')} {t.get('direction', '')}\n"
                f"  PnL: ${self._format_number(pnl or 0)}\n"
                f"  Strategy: {t.get('strategy_used', 'N/A')}"
            )
        return "\n".join(lines)

    def format_performance(self, metrics: dict) -> str:
        lines = [
            "📊 Performance",
            f"Total Trades: {metrics.get('total_trades', 0)}",
            f"Wins: {metrics.get('wins', 0)} | Losses: {metrics.get('losses', 0)}",
            f"Win Rate: {metrics.get('win_rate', 0) * 100:.0f}%",
            f"Total PnL: ${self._format_number(metrics.get('total_pnl', 0))}",
            f"Profit Factor: {metrics.get('profit_factor', 0):.2f}",
            f"Avg PnL: ${self._format_number(metrics.get('avg_pnl', 0))}",
        ]
        return "\n".join(lines)

    def format_playbook(self, playbook: dict) -> str:
        if not playbook:
            return "📭 No playbook found"
        lines = [
            "📖 Playbook",
            f"Version: {playbook.get('version', 'N/A')}",
            f"Triggered By: {playbook.get('triggered_by', 'N/A')}",
        ]
        if playbook.get("change_summary"):
            lines.append(f"Changes: {playbook['change_summary']}")
        pj = playbook.get("playbook_json", {})
        if pj.get("lessons"):
            lines.append("Lessons:")
            for lesson in pj["lessons"]:
                lines.append(f"  • {lesson}")
        if pj.get("regime_rules"):
            lines.append(f"Regime Rules: {len(pj['regime_rules'])} defined")
        return "\n".join(lines)

    def format_system_alert(self, alert: dict) -> str:
        severity = alert.get("severity", "INFO")
        emoji = {"CRITICAL": "🚨", "WARNING": "⚠️", "INFO": "ℹ️"}.get(severity, "ℹ️")
        lines = [
            f"{emoji} System Alert [{severity}]",
            f"Source: {alert.get('source', 'N/A')}",
            f"Message: {alert.get('message', 'N/A')}",
        ]
        return "\n".join(lines)

    def format_market_alert(self, alert: dict) -> str:
        alert_type = alert.get("alert_type", "unknown")
        symbol = alert.get("symbol", "N/A")
        lines = [
            f"📡 Market Alert: {alert_type}",
            f"Symbol: {symbol}",
            f"Message: {alert.get('message', 'N/A')}",
        ]
        if "value" in alert:
            lines.append(f"Value: {alert['value']}")
        return "\n".join(lines)

    def format_research_result(self, research: dict) -> str:
        lines = [
            "🔬 Research Result",
            f"Query: {research.get('query', 'N/A')}",
            f"Source: {research.get('source', 'N/A')}",
        ]
        summary = research.get("summary", "")
        if summary:
            lines.append(f"Summary: {summary}")
        else:
            lines.append("Summary: No results")
        return "\n".join(lines)

    def _format_number(self, value: float, decimals: int = 2) -> str:
        """Format number with commas: 102500.00 -> '102,500.00'"""
        return f"{value:,.{decimals}f}"

    def _format_pct(self, value: float) -> str:
        """Format percentage: 0.012 -> '+1.20%'"""
        pct = value * 100
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.2f}%"

    def _format_duration(self, seconds: int) -> str:
        """Format duration: 8100 -> '2h 15m'"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
