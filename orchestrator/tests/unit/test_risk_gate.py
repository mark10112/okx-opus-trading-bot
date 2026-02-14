"""Unit tests for RiskGate — boundary value testing for all 11 rules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from orchestrator.config import Settings
from orchestrator.risk_gate import RiskCheck, RiskGate, RiskResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings():
    """Default settings with known thresholds."""
    return Settings(
        MAX_DAILY_LOSS_PCT=0.03,
        MAX_SINGLE_TRADE_PCT=0.05,
        MAX_TOTAL_EXPOSURE_PCT=0.15,
        MAX_CONCURRENT_POSITIONS=3,
        MAX_DRAWDOWN_PCT=0.10,
        MAX_CONSECUTIVE_LOSSES=3,
        MAX_LEVERAGE=3.0,
        MAX_SL_DISTANCE_PCT=0.03,
        MIN_RR_RATIO=1.5,
        COOLDOWN_AFTER_LOSS_STREAK=1800,
    )


@pytest.fixture
def gate(settings):
    g = RiskGate(settings)
    g.daily_start_equity = 10000.0
    g.peak_equity = 10000.0
    return g


@pytest.fixture
def base_decision():
    """A valid decision dict that passes all checks."""
    return {
        "action": "OPEN_LONG",
        "symbol": "BTC-USDT-SWAP",
        "size_pct": 0.03,
        "entry_price": 60000.0,
        "stop_loss": 59000.0,
        "take_profit": 63000.0,
        "leverage": 2.0,
    }


@pytest.fixture
def base_account():
    return {"equity": 10000.0}


@pytest.fixture
def no_positions():
    return []


# ---------------------------------------------------------------------------
# 1. Max Daily Loss (-3% equity)
# ---------------------------------------------------------------------------


class TestCheckDailyLoss:
    def test_below_threshold_passes(self, gate):
        """Equity at 9800 = -2% loss (below 3%) -> pass."""
        result = gate._check_daily_loss({"equity": 9800.0})
        assert result.passed is True

    def test_at_threshold_fails(self, gate):
        """Equity at 9700 = exactly -3% loss -> fail."""
        result = gate._check_daily_loss({"equity": 9700.0})
        assert result.passed is False
        assert "daily_loss" in result.rule

    def test_above_threshold_fails(self, gate):
        """Equity at 9600 = -4% loss (above 3%) -> fail."""
        result = gate._check_daily_loss({"equity": 9600.0})
        assert result.passed is False

    def test_profit_passes(self, gate):
        """Equity at 10500 = +5% gain -> pass."""
        result = gate._check_daily_loss({"equity": 10500.0})
        assert result.passed is True

    def test_zero_start_equity_passes(self, gate):
        """If daily_start_equity is 0, skip check (pass)."""
        gate.daily_start_equity = 0.0
        result = gate._check_daily_loss({"equity": 5000.0})
        assert result.passed is True


# ---------------------------------------------------------------------------
# 2. Max Drawdown from Peak (-10% equity)
# ---------------------------------------------------------------------------


class TestCheckMaxDrawdown:
    def test_below_threshold_passes(self, gate):
        """Equity at 9200 = -8% from peak -> pass."""
        result = gate._check_max_drawdown({"equity": 9200.0})
        assert result.passed is True

    def test_at_threshold_fails(self, gate):
        """Equity at 9000 = exactly -10% from peak -> fail."""
        result = gate._check_max_drawdown({"equity": 9000.0})
        assert result.passed is False
        assert "max_drawdown" in result.rule

    def test_above_threshold_fails(self, gate):
        """Equity at 8500 = -15% from peak -> fail."""
        result = gate._check_max_drawdown({"equity": 8500.0})
        assert result.passed is False

    def test_at_peak_passes(self, gate):
        """Equity at peak -> pass."""
        result = gate._check_max_drawdown({"equity": 10000.0})
        assert result.passed is True

    def test_above_peak_passes(self, gate):
        """Equity above peak -> pass and updates peak."""
        result = gate._check_max_drawdown({"equity": 11000.0})
        assert result.passed is True

    def test_zero_peak_passes(self, gate):
        """If peak_equity is 0, skip check (pass)."""
        gate.peak_equity = 0.0
        result = gate._check_max_drawdown({"equity": 5000.0})
        assert result.passed is True


# ---------------------------------------------------------------------------
# 3. Max Concurrent Positions (3)
# ---------------------------------------------------------------------------


class TestCheckPositionCount:
    def test_below_limit_passes(self, gate):
        """2 positions < 3 -> pass."""
        positions = [{"instId": "BTC"}, {"instId": "ETH"}]
        result = gate._check_position_count(positions)
        assert result.passed is True

    def test_at_limit_fails(self, gate):
        """3 positions = limit -> fail (can't open more)."""
        positions = [{"instId": "BTC"}, {"instId": "ETH"}, {"instId": "SOL"}]
        result = gate._check_position_count(positions)
        assert result.passed is False
        assert "position_count" in result.rule

    def test_above_limit_fails(self, gate):
        """4 positions > 3 -> fail."""
        positions = [{"instId": f"P{i}"} for i in range(4)]
        result = gate._check_position_count(positions)
        assert result.passed is False

    def test_empty_passes(self, gate):
        """0 positions -> pass."""
        result = gate._check_position_count([])
        assert result.passed is True


# ---------------------------------------------------------------------------
# 4. Max Total Exposure (15% of equity)
# ---------------------------------------------------------------------------


class TestCheckTotalExposure:
    def test_below_threshold_passes(self, gate):
        """Total exposure 10% < 15% -> pass."""
        positions = [{"notionalUsd": 500.0}, {"notionalUsd": 500.0}]
        result = gate._check_total_exposure(positions, {"equity": 10000.0})
        assert result.passed is True

    def test_at_threshold_fails(self, gate):
        """Total exposure exactly 15% -> fail."""
        positions = [{"notionalUsd": 1500.0}]
        result = gate._check_total_exposure(positions, {"equity": 10000.0})
        assert result.passed is False
        assert "total_exposure" in result.rule

    def test_above_threshold_fails(self, gate):
        """Total exposure 20% > 15% -> fail."""
        positions = [{"notionalUsd": 2000.0}]
        result = gate._check_total_exposure(positions, {"equity": 10000.0})
        assert result.passed is False

    def test_empty_positions_passes(self, gate):
        """No positions -> 0% exposure -> pass."""
        result = gate._check_total_exposure([], {"equity": 10000.0})
        assert result.passed is True


# ---------------------------------------------------------------------------
# 5. Max Single Trade Size (5% of equity)
# ---------------------------------------------------------------------------


class TestCheckTradeSize:
    def test_below_threshold_passes(self, gate):
        """3% size < 5% -> pass."""
        result = gate._check_trade_size(
            {"size_pct": 0.03}, {"equity": 10000.0}
        )
        assert result.passed is True

    def test_at_threshold_fails(self, gate):
        """5% size = exactly threshold -> fail."""
        result = gate._check_trade_size(
            {"size_pct": 0.05}, {"equity": 10000.0}
        )
        assert result.passed is False
        assert "trade_size" in result.rule

    def test_above_threshold_fails(self, gate):
        """8% size > 5% -> fail."""
        result = gate._check_trade_size(
            {"size_pct": 0.08}, {"equity": 10000.0}
        )
        assert result.passed is False

    def test_zero_size_passes(self, gate):
        """0% size -> pass."""
        result = gate._check_trade_size(
            {"size_pct": 0.0}, {"equity": 10000.0}
        )
        assert result.passed is True


# ---------------------------------------------------------------------------
# 6. Max Leverage (3x)
# ---------------------------------------------------------------------------


class TestCheckLeverage:
    def test_below_limit_passes(self, gate):
        """2x leverage < 3x -> pass."""
        result = gate._check_leverage({"leverage": 2.0})
        assert result.passed is True

    def test_at_limit_fails(self, gate):
        """3x leverage = exactly limit -> fail."""
        result = gate._check_leverage({"leverage": 3.0})
        assert result.passed is False
        assert "leverage" in result.rule

    def test_above_limit_fails(self, gate):
        """5x leverage > 3x -> fail."""
        result = gate._check_leverage({"leverage": 5.0})
        assert result.passed is False

    def test_1x_passes(self, gate):
        """1x leverage -> pass."""
        result = gate._check_leverage({"leverage": 1.0})
        assert result.passed is True


# ---------------------------------------------------------------------------
# 7. Required Stop Loss
# ---------------------------------------------------------------------------


class TestCheckStopLoss:
    def test_with_stop_loss_passes(self, gate):
        """Decision with stop_loss > 0 -> pass."""
        result = gate._check_stop_loss({"stop_loss": 59000.0})
        assert result.passed is True

    def test_zero_stop_loss_fails(self, gate):
        """Decision with stop_loss = 0 -> fail."""
        result = gate._check_stop_loss({"stop_loss": 0.0})
        assert result.passed is False
        assert "stop_loss" in result.rule

    def test_missing_stop_loss_fails(self, gate):
        """Decision without stop_loss key -> fail."""
        result = gate._check_stop_loss({"entry_price": 60000.0})
        assert result.passed is False

    def test_none_stop_loss_fails(self, gate):
        """Decision with stop_loss = None -> fail."""
        result = gate._check_stop_loss({"stop_loss": None})
        assert result.passed is False


# ---------------------------------------------------------------------------
# 8. Max SL Distance (3% from entry)
# ---------------------------------------------------------------------------


class TestCheckSlDistance:
    def test_below_threshold_passes(self, gate):
        """SL at 1.5% from entry -> pass."""
        result = gate._check_sl_distance({
            "entry_price": 60000.0,
            "stop_loss": 59100.0,
            "action": "OPEN_LONG",
        })
        assert result.passed is True

    def test_at_threshold_fails(self, gate):
        """SL at exactly 3% from entry -> fail."""
        result = gate._check_sl_distance({
            "entry_price": 60000.0,
            "stop_loss": 58200.0,
            "action": "OPEN_LONG",
        })
        assert result.passed is False
        assert "sl_distance" in result.rule

    def test_above_threshold_fails(self, gate):
        """SL at 5% from entry -> fail."""
        result = gate._check_sl_distance({
            "entry_price": 60000.0,
            "stop_loss": 57000.0,
            "action": "OPEN_LONG",
        })
        assert result.passed is False

    def test_short_below_threshold_passes(self, gate):
        """Short: SL at 1% above entry -> pass."""
        result = gate._check_sl_distance({
            "entry_price": 60000.0,
            "stop_loss": 60600.0,
            "action": "OPEN_SHORT",
        })
        assert result.passed is True

    def test_short_at_threshold_fails(self, gate):
        """Short: SL at exactly 3% above entry -> fail."""
        result = gate._check_sl_distance({
            "entry_price": 60000.0,
            "stop_loss": 61800.0,
            "action": "OPEN_SHORT",
        })
        assert result.passed is False

    def test_missing_entry_price_passes(self, gate):
        """If entry_price is missing/0, skip check (pass)."""
        result = gate._check_sl_distance({
            "entry_price": 0.0,
            "stop_loss": 59000.0,
            "action": "OPEN_LONG",
        })
        assert result.passed is True


# ---------------------------------------------------------------------------
# 9. Min R:R Ratio (1.5:1)
# ---------------------------------------------------------------------------


class TestCheckRrRatio:
    def test_above_threshold_passes(self, gate):
        """R:R = 2.0 > 1.5 -> pass."""
        result = gate._check_rr_ratio({
            "entry_price": 60000.0,
            "stop_loss": 59000.0,
            "take_profit": 62000.0,
            "action": "OPEN_LONG",
        })
        assert result.passed is True

    def test_at_threshold_passes(self, gate):
        """R:R = exactly 1.5 -> pass (>= threshold)."""
        result = gate._check_rr_ratio({
            "entry_price": 60000.0,
            "stop_loss": 59000.0,
            "take_profit": 61500.0,
            "action": "OPEN_LONG",
        })
        assert result.passed is True

    def test_below_threshold_fails(self, gate):
        """R:R = 1.0 < 1.5 -> fail."""
        result = gate._check_rr_ratio({
            "entry_price": 60000.0,
            "stop_loss": 59000.0,
            "take_profit": 61000.0,
            "action": "OPEN_LONG",
        })
        assert result.passed is False
        assert "rr_ratio" in result.rule

    def test_no_take_profit_passes(self, gate):
        """If take_profit is missing/0, skip check (pass)."""
        result = gate._check_rr_ratio({
            "entry_price": 60000.0,
            "stop_loss": 59000.0,
            "take_profit": 0.0,
            "action": "OPEN_LONG",
        })
        assert result.passed is True

    def test_short_above_threshold_passes(self, gate):
        """Short: R:R = 2.0 > 1.5 -> pass."""
        result = gate._check_rr_ratio({
            "entry_price": 60000.0,
            "stop_loss": 61000.0,
            "take_profit": 58000.0,
            "action": "OPEN_SHORT",
        })
        assert result.passed is True

    def test_short_below_threshold_fails(self, gate):
        """Short: R:R = 0.5 < 1.5 -> fail."""
        result = gate._check_rr_ratio({
            "entry_price": 60000.0,
            "stop_loss": 61000.0,
            "take_profit": 59500.0,
            "action": "OPEN_SHORT",
        })
        assert result.passed is False


# ---------------------------------------------------------------------------
# 10. Consecutive Loss Cooldown (3 losses -> 30 min)
# ---------------------------------------------------------------------------


class TestCheckCooldown:
    def test_no_cooldown_passes(self, gate):
        """No cooldown active -> pass."""
        result = gate._check_cooldown()
        assert result.passed is True

    def test_active_cooldown_fails(self, gate):
        """Cooldown active (future time) -> fail."""
        gate.cooldown_until = datetime.now(timezone.utc) + timedelta(minutes=15)
        result = gate._check_cooldown()
        assert result.passed is False
        assert "cooldown" in result.rule

    def test_expired_cooldown_passes(self, gate):
        """Cooldown expired (past time) -> pass."""
        gate.cooldown_until = datetime.now(timezone.utc) - timedelta(minutes=5)
        result = gate._check_cooldown()
        assert result.passed is True


# ---------------------------------------------------------------------------
# 11. Correlated Position Check (WARNING only)
# ---------------------------------------------------------------------------


class TestCheckCorrelation:
    def test_no_positions_passes(self, gate):
        """No existing positions -> pass."""
        result = gate._check_correlation(
            {"symbol": "BTC-USDT-SWAP"}, []
        )
        assert result.passed is True

    def test_same_symbol_warns(self, gate):
        """Same symbol already in positions -> warning (still passes)."""
        positions = [{"instId": "BTC-USDT-SWAP"}]
        result = gate._check_correlation(
            {"symbol": "BTC-USDT-SWAP"}, positions
        )
        # Correlation is WARNING only, not reject
        assert result.passed is True
        assert "correlation" in result.rule

    def test_different_symbol_passes(self, gate):
        """Different symbol -> pass with no warning."""
        positions = [{"instId": "ETH-USDT-SWAP"}]
        result = gate._check_correlation(
            {"symbol": "BTC-USDT-SWAP"}, positions
        )
        assert result.passed is True


# ---------------------------------------------------------------------------
# validate() — aggregates all checks
# ---------------------------------------------------------------------------


class TestValidate:
    def test_valid_decision_approved(self, gate, base_decision, base_account, no_positions):
        """A valid decision should be approved."""
        result = gate.validate(base_decision, base_account, no_positions)
        assert isinstance(result, RiskResult)
        assert result.approved is True
        assert len(result.failures) == 0

    def test_multiple_failures(self, gate, base_account):
        """Decision with multiple violations should collect all failures."""
        bad_decision = {
            "action": "OPEN_LONG",
            "symbol": "BTC-USDT-SWAP",
            "size_pct": 0.10,  # > 5%
            "entry_price": 60000.0,
            "stop_loss": 0.0,  # missing SL
            "take_profit": 61000.0,
            "leverage": 5.0,  # > 3x
        }
        result = gate.validate(bad_decision, base_account, [])
        assert result.approved is False
        assert len(result.failures) >= 3  # trade_size, stop_loss, leverage

    def test_daily_loss_halt(self, gate, base_decision):
        """Daily loss exceeding threshold -> not approved."""
        account = {"equity": 9600.0}  # -4% from 10000
        result = gate.validate(base_decision, account, [])
        assert result.approved is False
        rules = [f.rule for f in result.failures]
        assert "daily_loss" in rules

    def test_max_drawdown_halt(self, gate, base_decision, base_account):
        """Drawdown exceeding threshold -> not approved."""
        gate.peak_equity = 12000.0
        account = {"equity": 10000.0}  # -16.7% from peak
        result = gate.validate(base_decision, account, [])
        assert result.approved is False
        rules = [f.rule for f in result.failures]
        assert "max_drawdown" in rules

    def test_cooldown_rejects(self, gate, base_decision, base_account, no_positions):
        """Active cooldown -> not approved."""
        gate.cooldown_until = datetime.now(timezone.utc) + timedelta(minutes=10)
        result = gate.validate(base_decision, base_account, no_positions)
        assert result.approved is False
        rules = [f.rule for f in result.failures]
        assert "cooldown" in rules

    def test_hold_action_skips_validation(self, gate, base_account, no_positions):
        """HOLD action should always be approved (no trade to validate)."""
        hold_decision = {
            "action": "HOLD",
            "symbol": "BTC-USDT-SWAP",
            "size_pct": 0.0,
            "entry_price": 0.0,
            "stop_loss": 0.0,
            "take_profit": 0.0,
            "leverage": 1.0,
        }
        result = gate.validate(hold_decision, base_account, no_positions)
        assert result.approved is True

    def test_close_action_skips_trade_checks(self, gate, base_account, no_positions):
        """CLOSE action should skip size/SL/TP/leverage checks."""
        close_decision = {
            "action": "CLOSE",
            "symbol": "BTC-USDT-SWAP",
            "size_pct": 0.0,
            "entry_price": 0.0,
            "stop_loss": 0.0,
            "take_profit": 0.0,
            "leverage": 1.0,
        }
        result = gate.validate(close_decision, base_account, no_positions)
        assert result.approved is True

    def test_correlation_warning_still_approved(self, gate, base_decision, base_account):
        """Correlation warning should not reject, but appear in warnings."""
        positions = [{"instId": "BTC-USDT-SWAP", "notionalUsd": 500.0}]
        result = gate.validate(base_decision, base_account, positions)
        assert result.approved is True
        warning_rules = [w.rule for w in result.warnings]
        assert "correlation" in warning_rules


# ---------------------------------------------------------------------------
# update_on_trade_close()
# ---------------------------------------------------------------------------


class TestUpdateOnTradeClose:
    def test_loss_increments_counter(self, gate):
        """Negative PnL should increment consecutive_losses."""
        gate.update_on_trade_close(-100.0)
        assert gate.consecutive_losses == 1

    def test_win_resets_counter(self, gate):
        """Positive PnL should reset consecutive_losses to 0."""
        gate.consecutive_losses = 2
        gate.update_on_trade_close(100.0)
        assert gate.consecutive_losses == 0

    def test_three_losses_triggers_cooldown(self, gate, settings):
        """3 consecutive losses should set cooldown_until."""
        gate.update_on_trade_close(-50.0)
        gate.update_on_trade_close(-50.0)
        gate.update_on_trade_close(-50.0)
        assert gate.cooldown_until is not None
        assert gate.cooldown_until > datetime.now(timezone.utc)

    def test_peak_equity_updated_on_win(self, gate):
        """Peak equity should update when equity increases."""
        gate.peak_equity = 10000.0
        gate.update_on_trade_close(500.0)
        # consecutive_losses reset
        assert gate.consecutive_losses == 0

    def test_zero_pnl_resets_counter(self, gate):
        """Zero PnL (breakeven) should reset consecutive_losses."""
        gate.consecutive_losses = 2
        gate.update_on_trade_close(0.0)
        assert gate.consecutive_losses == 0


# ---------------------------------------------------------------------------
# reset_daily()
# ---------------------------------------------------------------------------


class TestResetDaily:
    def test_reset_sets_daily_start(self, gate):
        """reset_daily() should update daily_start_equity to current value."""
        gate.daily_start_equity = 10000.0
        gate.reset_daily(10500.0)
        assert gate.daily_start_equity == 10500.0

    def test_reset_clears_cooldown(self, gate):
        """reset_daily() should clear any active cooldown."""
        gate.cooldown_until = datetime.now(timezone.utc) + timedelta(hours=1)
        gate.reset_daily(10000.0)
        assert gate.cooldown_until is None
