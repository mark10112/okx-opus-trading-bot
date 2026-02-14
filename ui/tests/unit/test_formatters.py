"""Unit tests for telegram/formatters.py — message formatting."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ui.telegram.formatters import MessageFormatter


@pytest.fixture
def fmt():
    return MessageFormatter()


# ─── Private helpers ───


class TestFormatNumber:
    def test_basic(self, fmt):
        assert fmt._format_number(102500.0) == "102,500.00"

    def test_zero(self, fmt):
        assert fmt._format_number(0.0) == "0.00"

    def test_negative(self, fmt):
        assert fmt._format_number(-1234.5) == "-1,234.50"

    def test_custom_decimals(self, fmt):
        assert fmt._format_number(99999.1234, decimals=4) == "99,999.1234"

    def test_large_number(self, fmt):
        assert fmt._format_number(1000000.0) == "1,000,000.00"


class TestFormatPct:
    def test_positive(self, fmt):
        assert fmt._format_pct(0.012) == "+1.20%"

    def test_negative(self, fmt):
        assert fmt._format_pct(-0.035) == "-3.50%"

    def test_zero(self, fmt):
        assert fmt._format_pct(0.0) == "+0.00%"

    def test_small_value(self, fmt):
        assert fmt._format_pct(0.001) == "+0.10%"


class TestFormatDuration:
    def test_hours_and_minutes(self, fmt):
        assert fmt._format_duration(8100) == "2h 15m"

    def test_minutes_only(self, fmt):
        assert fmt._format_duration(300) == "5m"

    def test_hours_only(self, fmt):
        assert fmt._format_duration(7200) == "2h 0m"

    def test_zero(self, fmt):
        assert fmt._format_duration(0) == "0m"

    def test_days(self, fmt):
        assert fmt._format_duration(90000) == "25h 0m"


# ─── format_status ───


class TestFormatStatus:
    def test_contains_equity(self, fmt):
        text = fmt.format_status(
            equity=105000.0,
            daily_pnl=500.0,
            positions=[{"symbol": "BTC-USDT-SWAP"}],
            state="IDLE",
            last_decision={"strategy": "momentum", "confidence": 0.8},
            screener_rate=0.2,
        )
        assert "105,000.00" in text
        assert "500.00" in text

    def test_contains_state(self, fmt):
        text = fmt.format_status(
            equity=100000.0,
            daily_pnl=0.0,
            positions=[],
            state="HALTED",
            last_decision=None,
            screener_rate=0.0,
        )
        assert "HALTED" in text

    def test_contains_position_count(self, fmt):
        text = fmt.format_status(
            equity=100000.0,
            daily_pnl=0.0,
            positions=[{"symbol": "BTC"}, {"symbol": "ETH"}],
            state="IDLE",
            last_decision=None,
            screener_rate=0.15,
        )
        assert "2" in text

    def test_contains_screener_rate(self, fmt):
        text = fmt.format_status(
            equity=100000.0,
            daily_pnl=0.0,
            positions=[],
            state="IDLE",
            last_decision=None,
            screener_rate=0.25,
        )
        assert "25" in text


# ─── format_positions ───


class TestFormatPositions:
    def test_single_position(self, fmt):
        positions = [
            {
                "symbol": "BTC-USDT-SWAP",
                "direction": "LONG",
                "entry_price": 100000.0,
                "size": 0.01,
                "leverage": 2.0,
                "pnl_usd": 150.0,
                "stop_loss": 98000.0,
                "take_profit": 105000.0,
            }
        ]
        text = fmt.format_positions(positions)
        assert "BTC-USDT-SWAP" in text
        assert "LONG" in text
        assert "100,000" in text

    def test_empty_positions(self, fmt):
        text = fmt.format_positions([])
        assert "no" in text.lower() or "empty" in text.lower() or "none" in text.lower()

    def test_multiple_positions(self, fmt):
        positions = [
            {
                "symbol": "BTC-USDT-SWAP",
                "direction": "LONG",
                "entry_price": 100000.0,
                "size": 0.01,
                "leverage": 2.0,
                "pnl_usd": 50.0,
                "stop_loss": 98000.0,
                "take_profit": 105000.0,
            },
            {
                "symbol": "ETH-USDT-SWAP",
                "direction": "SHORT",
                "entry_price": 3500.0,
                "size": 0.1,
                "leverage": 3.0,
                "pnl_usd": -20.0,
                "stop_loss": 3600.0,
                "take_profit": 3200.0,
            },
        ]
        text = fmt.format_positions(positions)
        assert "BTC-USDT-SWAP" in text
        assert "ETH-USDT-SWAP" in text


# ─── format_trade_fill ───


class TestFormatTradeFill:
    def test_contains_fill_info(self, fmt):
        fill = {
            "symbol": "BTC-USDT-SWAP",
            "direction": "LONG",
            "action": "OPEN_LONG",
            "entry_price": 100000.0,
            "size": 0.01,
            "leverage": 2.0,
            "strategy": "momentum",
        }
        text = fmt.format_trade_fill(fill)
        assert "BTC-USDT-SWAP" in text
        assert "LONG" in text or "OPEN" in text

    def test_close_fill(self, fmt):
        fill = {
            "symbol": "BTC-USDT-SWAP",
            "direction": "LONG",
            "action": "CLOSE",
            "exit_price": 101000.0,
            "pnl_usd": 100.0,
            "size": 0.01,
        }
        text = fmt.format_trade_fill(fill)
        assert "CLOSE" in text or "close" in text.lower()


# ─── format_position_closed ───


class TestFormatPositionClosed:
    def test_profit(self, fmt):
        pos = {
            "symbol": "BTC-USDT-SWAP",
            "direction": "LONG",
            "entry_price": 100000.0,
            "exit_price": 101000.0,
            "pnl_usd": 100.0,
            "pnl_pct": 0.01,
            "duration_seconds": 3600,
            "strategy_used": "momentum",
            "exit_reason": "take_profit",
        }
        text = fmt.format_position_closed(pos)
        assert "100.00" in text
        assert "BTC-USDT-SWAP" in text

    def test_loss(self, fmt):
        pos = {
            "symbol": "BTC-USDT-SWAP",
            "direction": "SHORT",
            "entry_price": 100000.0,
            "exit_price": 101000.0,
            "pnl_usd": -100.0,
            "pnl_pct": -0.01,
            "duration_seconds": 1800,
            "strategy_used": "mean_reversion",
            "exit_reason": "stop_loss",
        }
        text = fmt.format_position_closed(pos)
        assert "-100.00" in text


# ─── format_trades_list ───


class TestFormatTradesList:
    def test_with_trades(self, fmt):
        trades = [
            {
                "trade_id": "t-001",
                "symbol": "BTC-USDT-SWAP",
                "direction": "LONG",
                "pnl_usd": 50.0,
                "strategy_used": "momentum",
                "opened_at": datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
                "closed_at": datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
            },
            {
                "trade_id": "t-002",
                "symbol": "BTC-USDT-SWAP",
                "direction": "SHORT",
                "pnl_usd": -30.0,
                "strategy_used": "mean_reversion",
                "opened_at": datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                "closed_at": datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc),
            },
        ]
        text = fmt.format_trades_list(trades)
        assert "t-001" in text or "BTC" in text
        assert "50.00" in text

    def test_empty_trades(self, fmt):
        text = fmt.format_trades_list([])
        assert "no" in text.lower() or "empty" in text.lower() or "none" in text.lower()


# ─── format_performance ───


class TestFormatPerformance:
    def test_with_metrics(self, fmt):
        metrics = {
            "total_trades": 50,
            "wins": 35,
            "losses": 15,
            "win_rate": 0.7,
            "total_pnl": 1500.0,
            "profit_factor": 3.5,
            "avg_pnl": 30.0,
        }
        text = fmt.format_performance(metrics)
        assert "50" in text
        assert "70" in text  # win rate as pct
        assert "1,500.00" in text

    def test_zero_metrics(self, fmt):
        metrics = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "profit_factor": 0.0,
            "avg_pnl": 0.0,
        }
        text = fmt.format_performance(metrics)
        assert "0" in text


# ─── format_playbook ───


class TestFormatPlaybook:
    def test_with_playbook(self, fmt):
        playbook = {
            "version": 5,
            "playbook_json": {
                "regime_rules": {"trending_up": {"strategies": ["momentum"]}},
                "lessons": ["Cut losses early", "Follow the trend"],
            },
            "change_summary": "Updated after deep reflection",
            "triggered_by": "reflection",
        }
        text = fmt.format_playbook(playbook)
        assert "5" in text
        assert "reflection" in text.lower() or "Reflection" in text

    def test_empty_playbook(self, fmt):
        text = fmt.format_playbook({})
        assert "no" in text.lower() or "none" in text.lower() or "empty" in text.lower()


# ─── format_system_alert ───


class TestFormatSystemAlert:
    def test_halt_alert(self, fmt):
        alert = {
            "severity": "CRITICAL",
            "message": "Max daily loss exceeded",
            "source": "risk_gate",
        }
        text = fmt.format_system_alert(alert)
        assert "CRITICAL" in text
        assert "Max daily loss" in text

    def test_info_alert(self, fmt):
        alert = {
            "severity": "INFO",
            "message": "Bot resumed",
            "source": "admin",
        }
        text = fmt.format_system_alert(alert)
        assert "Bot resumed" in text


# ─── format_market_alert ───


class TestFormatMarketAlert:
    def test_price_alert(self, fmt):
        alert = {
            "alert_type": "price_change",
            "symbol": "BTC-USDT-SWAP",
            "message": "Price moved +3.5% in 1H",
            "value": 3.5,
        }
        text = fmt.format_market_alert(alert)
        assert "BTC-USDT-SWAP" in text
        assert "3.5" in text

    def test_funding_alert(self, fmt):
        alert = {
            "alert_type": "funding_spike",
            "symbol": "BTC-USDT-SWAP",
            "message": "Funding rate 0.08%",
            "value": 0.08,
        }
        text = fmt.format_market_alert(alert)
        assert "funding" in text.lower() or "Funding" in text


# ─── format_research_result ───


class TestFormatResearchResult:
    def test_with_result(self, fmt):
        research = {
            "query": "BTC market outlook after CPI",
            "summary": "Markets expect dovish Fed stance",
            "source": "perplexity",
        }
        text = fmt.format_research_result(research)
        assert "BTC market outlook" in text or "dovish" in text

    def test_empty_result(self, fmt):
        research = {
            "query": "test query",
            "summary": "",
            "source": "perplexity",
        }
        text = fmt.format_research_result(research)
        assert "test query" in text or "no" in text.lower()
