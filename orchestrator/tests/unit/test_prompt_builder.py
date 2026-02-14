"""Unit tests for PromptBuilder — XML-structured prompts for Opus analysis/reflection."""

from __future__ import annotations

import pytest

from orchestrator.prompt_builder import PromptBuilder


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def builder():
    return PromptBuilder()


@pytest.fixture
def sample_snapshot():
    return {
        "ticker": {"symbol": "BTC-USDT-SWAP", "last": 60000.0, "bid": 59999.0, "ask": 60001.0},
        "indicators": {
            "5m": {
                "rsi": 55.0,
                "macd": {"line": 100.0, "signal": 80.0, "histogram": 20.0},
                "bollinger": {"upper": 61000.0, "middle": 60000.0, "lower": 59000.0},
                "ema": {20: 59800.0, 50: 59500.0, 200: 58000.0},
                "atr": 200.0,
                "adx": 30.0,
                "bb_position": "middle",
                "ema_alignment": "bullish",
                "macd_signal": "bullish",
            },
            "1H": {
                "rsi": 62.0,
                "macd": {"line": 150.0, "signal": 120.0, "histogram": 30.0},
                "bollinger": {"upper": 62000.0, "middle": 60500.0, "lower": 59000.0},
                "ema": {20: 60000.0, 50: 59000.0, 200: 57000.0},
                "atr": 500.0,
                "adx": 35.0,
                "bb_position": "upper",
                "ema_alignment": "bullish",
                "macd_signal": "bullish",
            },
        },
        "market_regime": "trending_up",
        "funding_rate": {"current": 0.0001, "predicted": 0.00012},
        "open_interest": {"oi": 5000000000, "oi_change_24h": 0.05},
        "long_short_ratio": 1.2,
        "price_change_1h": 0.015,
        "orderbook": {"spread": 2.0, "bid_depth": 1000000, "ask_depth": 900000},
    }


@pytest.fixture
def sample_positions():
    return [
        {
            "instId": "BTC-USDT-SWAP",
            "posSide": "long",
            "pos": "0.1",
            "avgPx": "59000.0",
            "upl": "100.0",
            "lever": "2",
        }
    ]


@pytest.fixture
def sample_account():
    return {
        "equity": 10000.0,
        "available_balance": 8000.0,
        "daily_pnl": 150.0,
        "max_drawdown_today": 0.005,
    }


@pytest.fixture
def sample_playbook():
    return {
        "version": 1,
        "market_regime_rules": {
            "trending_up": {
                "preferred_strategies": ["momentum", "breakout"],
                "avoid_strategies": ["mean_reversion"],
                "max_position_pct": 0.05,
            },
        },
        "strategy_definitions": {
            "momentum": {
                "entry": "EMA20 > EMA50 > EMA200, RSI 40-70",
                "exit": "RSI > 80 or trailing SL",
            },
        },
        "lessons_learned": [
            {"lesson": "Avoid trading during low volume hours", "impact": "high"},
        ],
    }


@pytest.fixture
def sample_recent_trades():
    return [
        {
            "trade_id": "t-1",
            "symbol": "BTC-USDT-SWAP",
            "direction": "LONG",
            "entry_price": 58000.0,
            "exit_price": 59500.0,
            "pnl_usd": 150.0,
            "pnl_pct": 0.026,
            "strategy_used": "momentum",
            "confidence_at_entry": 0.75,
        },
        {
            "trade_id": "t-2",
            "symbol": "BTC-USDT-SWAP",
            "direction": "SHORT",
            "entry_price": 61000.0,
            "exit_price": 61500.0,
            "pnl_usd": -50.0,
            "pnl_pct": -0.008,
            "strategy_used": "mean_reversion",
            "confidence_at_entry": 0.60,
        },
    ]


@pytest.fixture
def sample_research():
    return {
        "summary": "Fed signals potential rate pause, crypto markets react positively.",
        "sentiment": "bullish",
        "impact_level": "high",
        "key_points": ["Rate pause likely", "Institutional inflows increasing"],
    }


@pytest.fixture
def sample_trade():
    return {
        "trade_id": "t-3",
        "symbol": "BTC-USDT-SWAP",
        "direction": "LONG",
        "entry_price": 59000.0,
        "exit_price": 60500.0,
        "stop_loss": 58000.0,
        "take_profit": 62000.0,
        "pnl_usd": 150.0,
        "pnl_pct": 0.025,
        "strategy_used": "momentum",
        "confidence_at_entry": 0.80,
        "market_regime": "trending_up",
        "leverage": 2.0,
        "size_pct": 0.03,
        "duration_seconds": 3600,
    }


@pytest.fixture
def sample_performance():
    return {
        "total_trades": 25,
        "win_rate": 0.60,
        "profit_factor": 1.8,
        "sharpe_ratio": 1.5,
        "total_pnl_usd": 500.0,
        "avg_win": 80.0,
        "avg_loss": -45.0,
        "by_strategy": {
            "momentum": {"trades": 15, "win_rate": 0.67, "pnl": 400.0},
            "mean_reversion": {"trades": 10, "win_rate": 0.50, "pnl": 100.0},
        },
        "by_regime": {
            "trending_up": {"trades": 12, "win_rate": 0.75, "pnl": 350.0},
            "ranging": {"trades": 13, "win_rate": 0.46, "pnl": 150.0},
        },
    }


# ---------------------------------------------------------------------------
# build_analysis_prompt()
# ---------------------------------------------------------------------------


class TestBuildAnalysisPrompt:
    def test_returns_string(
        self,
        builder,
        sample_snapshot,
        sample_positions,
        sample_account,
        sample_research,
        sample_playbook,
        sample_recent_trades,
    ):
        result = builder.build_analysis_prompt(
            snapshot=sample_snapshot,
            positions=sample_positions,
            account=sample_account,
            research=sample_research,
            playbook=sample_playbook,
            recent_trades=sample_recent_trades,
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_market_snapshot_section(
        self,
        builder,
        sample_snapshot,
        sample_positions,
        sample_account,
        sample_research,
        sample_playbook,
        sample_recent_trades,
    ):
        result = builder.build_analysis_prompt(
            snapshot=sample_snapshot,
            positions=sample_positions,
            account=sample_account,
            research=sample_research,
            playbook=sample_playbook,
            recent_trades=sample_recent_trades,
        )
        assert "<market_snapshot>" in result
        assert "</market_snapshot>" in result

    def test_contains_technical_indicators_section(
        self,
        builder,
        sample_snapshot,
        sample_positions,
        sample_account,
        sample_research,
        sample_playbook,
        sample_recent_trades,
    ):
        result = builder.build_analysis_prompt(
            snapshot=sample_snapshot,
            positions=sample_positions,
            account=sample_account,
            research=sample_research,
            playbook=sample_playbook,
            recent_trades=sample_recent_trades,
        )
        assert "<technical_indicators>" in result
        assert "</technical_indicators>" in result

    def test_contains_current_positions_section(
        self,
        builder,
        sample_snapshot,
        sample_positions,
        sample_account,
        sample_research,
        sample_playbook,
        sample_recent_trades,
    ):
        result = builder.build_analysis_prompt(
            snapshot=sample_snapshot,
            positions=sample_positions,
            account=sample_account,
            research=sample_research,
            playbook=sample_playbook,
            recent_trades=sample_recent_trades,
        )
        assert "<current_positions>" in result
        assert "</current_positions>" in result

    def test_contains_account_state_section(
        self,
        builder,
        sample_snapshot,
        sample_positions,
        sample_account,
        sample_research,
        sample_playbook,
        sample_recent_trades,
    ):
        result = builder.build_analysis_prompt(
            snapshot=sample_snapshot,
            positions=sample_positions,
            account=sample_account,
            research=sample_research,
            playbook=sample_playbook,
            recent_trades=sample_recent_trades,
        )
        assert "<account_state>" in result
        assert "</account_state>" in result

    def test_contains_research_context_section(
        self,
        builder,
        sample_snapshot,
        sample_positions,
        sample_account,
        sample_research,
        sample_playbook,
        sample_recent_trades,
    ):
        result = builder.build_analysis_prompt(
            snapshot=sample_snapshot,
            positions=sample_positions,
            account=sample_account,
            research=sample_research,
            playbook=sample_playbook,
            recent_trades=sample_recent_trades,
        )
        assert "<research_context>" in result
        assert "</research_context>" in result

    def test_contains_playbook_section(
        self,
        builder,
        sample_snapshot,
        sample_positions,
        sample_account,
        sample_research,
        sample_playbook,
        sample_recent_trades,
    ):
        result = builder.build_analysis_prompt(
            snapshot=sample_snapshot,
            positions=sample_positions,
            account=sample_account,
            research=sample_research,
            playbook=sample_playbook,
            recent_trades=sample_recent_trades,
        )
        assert "<playbook>" in result
        assert "</playbook>" in result

    def test_contains_recent_trades_section(
        self,
        builder,
        sample_snapshot,
        sample_positions,
        sample_account,
        sample_research,
        sample_playbook,
        sample_recent_trades,
    ):
        result = builder.build_analysis_prompt(
            snapshot=sample_snapshot,
            positions=sample_positions,
            account=sample_account,
            research=sample_research,
            playbook=sample_playbook,
            recent_trades=sample_recent_trades,
        )
        assert "<recent_trades>" in result
        assert "</recent_trades>" in result

    def test_contains_output_format_section(
        self,
        builder,
        sample_snapshot,
        sample_positions,
        sample_account,
        sample_research,
        sample_playbook,
        sample_recent_trades,
    ):
        result = builder.build_analysis_prompt(
            snapshot=sample_snapshot,
            positions=sample_positions,
            account=sample_account,
            research=sample_research,
            playbook=sample_playbook,
            recent_trades=sample_recent_trades,
        )
        assert "<output_format>" in result
        assert "</output_format>" in result

    def test_none_research_omits_content(
        self,
        builder,
        sample_snapshot,
        sample_positions,
        sample_account,
        sample_playbook,
        sample_recent_trades,
    ):
        """When research is None, section should indicate no research available."""
        result = builder.build_analysis_prompt(
            snapshot=sample_snapshot,
            positions=sample_positions,
            account=sample_account,
            research=None,
            playbook=sample_playbook,
            recent_trades=sample_recent_trades,
        )
        assert "<research_context>" in result
        assert "No research" in result or "no research" in result or "None" in result

    def test_empty_positions(
        self,
        builder,
        sample_snapshot,
        sample_account,
        sample_research,
        sample_playbook,
        sample_recent_trades,
    ):
        """Empty positions list should still produce valid prompt."""
        result = builder.build_analysis_prompt(
            snapshot=sample_snapshot,
            positions=[],
            account=sample_account,
            research=sample_research,
            playbook=sample_playbook,
            recent_trades=sample_recent_trades,
        )
        assert "<current_positions>" in result
        assert (
            "No open positions" in result
            or "no open positions" in result
            or "none" in result.lower()
        )

    def test_empty_trades_list(
        self,
        builder,
        sample_snapshot,
        sample_positions,
        sample_account,
        sample_research,
        sample_playbook,
    ):
        """Empty recent trades should still produce valid prompt."""
        result = builder.build_analysis_prompt(
            snapshot=sample_snapshot,
            positions=sample_positions,
            account=sample_account,
            research=sample_research,
            playbook=sample_playbook,
            recent_trades=[],
        )
        assert "<recent_trades>" in result


# ---------------------------------------------------------------------------
# build_post_trade_prompt()
# ---------------------------------------------------------------------------


class TestBuildPostTradePrompt:
    def test_returns_string(self, builder, sample_trade):
        result = builder.build_post_trade_prompt(
            trade=sample_trade,
            indicators_entry={"rsi": 55.0, "adx": 30.0},
            indicators_exit={"rsi": 72.0, "adx": 28.0},
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_completed_trade_section(self, builder, sample_trade):
        result = builder.build_post_trade_prompt(
            trade=sample_trade,
            indicators_entry={"rsi": 55.0},
            indicators_exit={"rsi": 72.0},
        )
        assert "<completed_trade>" in result
        assert "</completed_trade>" in result

    def test_contains_output_format(self, builder, sample_trade):
        result = builder.build_post_trade_prompt(
            trade=sample_trade,
            indicators_entry={"rsi": 55.0},
            indicators_exit={"rsi": 72.0},
        )
        assert "<output_format>" in result
        assert "</output_format>" in result

    def test_includes_trade_details(self, builder, sample_trade):
        result = builder.build_post_trade_prompt(
            trade=sample_trade,
            indicators_entry={"rsi": 55.0},
            indicators_exit={"rsi": 72.0},
        )
        assert "BTC-USDT-SWAP" in result
        assert "LONG" in result


# ---------------------------------------------------------------------------
# build_deep_reflection_prompt()
# ---------------------------------------------------------------------------


class TestBuildDeepReflectionPrompt:
    def test_returns_string(
        self, builder, sample_recent_trades, sample_playbook, sample_performance
    ):
        result = builder.build_deep_reflection_prompt(
            trades=sample_recent_trades,
            playbook=sample_playbook,
            performance=sample_performance,
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_performance_summary(
        self, builder, sample_recent_trades, sample_playbook, sample_performance
    ):
        result = builder.build_deep_reflection_prompt(
            trades=sample_recent_trades,
            playbook=sample_playbook,
            performance=sample_performance,
        )
        assert "<performance_summary>" in result
        assert "</performance_summary>" in result

    def test_contains_breakdown_by_strategy(
        self, builder, sample_recent_trades, sample_playbook, sample_performance
    ):
        result = builder.build_deep_reflection_prompt(
            trades=sample_recent_trades,
            playbook=sample_playbook,
            performance=sample_performance,
        )
        assert "<breakdown_by_strategy>" in result
        assert "</breakdown_by_strategy>" in result

    def test_contains_breakdown_by_regime(
        self, builder, sample_recent_trades, sample_playbook, sample_performance
    ):
        result = builder.build_deep_reflection_prompt(
            trades=sample_recent_trades,
            playbook=sample_playbook,
            performance=sample_performance,
        )
        assert "<breakdown_by_regime>" in result
        assert "</breakdown_by_regime>" in result

    def test_contains_current_playbook(
        self, builder, sample_recent_trades, sample_playbook, sample_performance
    ):
        result = builder.build_deep_reflection_prompt(
            trades=sample_recent_trades,
            playbook=sample_playbook,
            performance=sample_performance,
        )
        assert "<current_playbook>" in result
        assert "</current_playbook>" in result

    def test_contains_tasks(
        self, builder, sample_recent_trades, sample_playbook, sample_performance
    ):
        result = builder.build_deep_reflection_prompt(
            trades=sample_recent_trades,
            playbook=sample_playbook,
            performance=sample_performance,
        )
        assert "<tasks>" in result
        assert "</tasks>" in result


# ---------------------------------------------------------------------------
# build_research_query()
# ---------------------------------------------------------------------------


class TestBuildResearchQuery:
    def test_returns_string(self, builder, sample_snapshot):
        result = builder.build_research_query(sample_snapshot)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_symbol(self, builder, sample_snapshot):
        result = builder.build_research_query(sample_snapshot)
        assert "BTC" in result

    def test_includes_regime(self, builder, sample_snapshot):
        result = builder.build_research_query(sample_snapshot)
        assert "trending" in result.lower() or "regime" in result.lower()
