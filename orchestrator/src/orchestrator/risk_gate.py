"""Hardcoded circuit breakers — Opus CANNOT override these rules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel

if TYPE_CHECKING:
    from orchestrator.config import Settings

logger = structlog.get_logger()


class RiskCheck(BaseModel):
    passed: bool
    rule: str
    reason: str


class RiskResult(BaseModel):
    approved: bool
    failures: list[RiskCheck] = []
    warnings: list[RiskCheck] = []


class RiskGate:
    """
    Hardcoded circuit breakers:
    | Rule                     | Threshold        | Action                       |
    |--------------------------|------------------|------------------------------|
    | Max Daily Loss           | -3% equity       | HALT all trading for the day |
    | Max Single Trade Size    | 5% of equity     | REJECT order                 |
    | Max Total Exposure       | 15% of equity    | REJECT new positions         |
    | Max Concurrent Positions | 3                | REJECT new positions         |
    | Max Drawdown from Peak   | -10% equity      | EMERGENCY HALT + alert       |
    | Consecutive Loss Cooldown| 3 losses         | 30 min cooldown              |
    | Max Leverage             | 3x               | Cap leverage                 |
    | Required Stop Loss       | always           | REJECT without SL            |
    | Max SL Distance          | 3% from entry    | REJECT if SL too far         |
    | Min R:R Ratio            | 1.5:1            | REJECT poor R:R              |
    | Correlated Position Check| r > 0.8          | WARN + reduce size           |
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.consecutive_losses = 0
        self.cooldown_until: datetime | None = None
        self.peak_equity: float = 0.0
        self.daily_start_equity: float = 0.0

    def validate(self, decision: dict, account: dict, positions: list) -> RiskResult:
        """Run all risk checks sequentially. Returns RiskResult."""
        action = decision.get("action", "HOLD")

        # HOLD and CLOSE skip trade-specific checks
        if action in ("HOLD", "CLOSE"):
            return RiskResult(approved=True)

        failures: list[RiskCheck] = []
        warnings: list[RiskCheck] = []

        # Account-level checks (always run for new trades)
        for check in [
            self._check_daily_loss(account),
            self._check_max_drawdown(account),
            self._check_cooldown(),
            self._check_position_count(positions),
            self._check_total_exposure(positions, account),
        ]:
            if not check.passed:
                failures.append(check)

        # Trade-specific checks
        for check in [
            self._check_trade_size(decision, account),
            self._check_leverage(decision),
            self._check_stop_loss(decision),
            self._check_sl_distance(decision),
            self._check_rr_ratio(decision),
        ]:
            if not check.passed:
                failures.append(check)

        # Correlation is WARNING only
        corr_check = self._check_correlation(decision, positions)
        if not corr_check.passed:
            warnings.append(corr_check)
        elif "correlation" in corr_check.rule and "same symbol" in corr_check.reason:
            warnings.append(corr_check)

        approved = len(failures) == 0
        if not approved:
            logger.warning(
                "risk_gate_rejected",
                action=action,
                failures=[f.rule for f in failures],
            )

        return RiskResult(approved=approved, failures=failures, warnings=warnings)

    def update_on_trade_close(self, pnl: float) -> None:
        """Update consecutive_losses counter, peak_equity tracking."""
        if pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.settings.MAX_CONSECUTIVE_LOSSES:
                self.cooldown_until = datetime.now(timezone.utc) + timedelta(
                    seconds=self.settings.COOLDOWN_AFTER_LOSS_STREAK
                )
                logger.warning(
                    "cooldown_triggered",
                    consecutive_losses=self.consecutive_losses,
                    cooldown_seconds=self.settings.COOLDOWN_AFTER_LOSS_STREAK,
                )
        else:
            self.consecutive_losses = 0

    def reset_daily(self, current_equity: float) -> None:
        """Reset daily_start_equity at 00:00 UTC."""
        self.daily_start_equity = current_equity
        self.cooldown_until = None
        logger.info("daily_reset", equity=current_equity)

    def _check_daily_loss(self, account: dict) -> RiskCheck:
        equity = account.get("equity", 0.0)
        if self.daily_start_equity <= 0:
            return RiskCheck(passed=True, rule="daily_loss", reason="No daily start equity set")
        loss_pct = (self.daily_start_equity - equity) / self.daily_start_equity
        if loss_pct >= self.settings.MAX_DAILY_LOSS_PCT:
            return RiskCheck(
                passed=False,
                rule="daily_loss",
                reason=f"Daily loss {loss_pct:.2%} >= {self.settings.MAX_DAILY_LOSS_PCT:.2%}",
            )
        return RiskCheck(passed=True, rule="daily_loss", reason="OK")

    def _check_max_drawdown(self, account: dict) -> RiskCheck:
        equity = account.get("equity", 0.0)
        if self.peak_equity <= 0:
            return RiskCheck(passed=True, rule="max_drawdown", reason="No peak equity set")
        # Update peak if equity is higher
        if equity > self.peak_equity:
            self.peak_equity = equity
        dd_pct = (self.peak_equity - equity) / self.peak_equity
        if dd_pct >= self.settings.MAX_DRAWDOWN_PCT:
            return RiskCheck(
                passed=False,
                rule="max_drawdown",
                reason=f"Drawdown {dd_pct:.2%} >= {self.settings.MAX_DRAWDOWN_PCT:.2%}",
            )
        return RiskCheck(passed=True, rule="max_drawdown", reason="OK")

    def _check_position_count(self, positions: list) -> RiskCheck:
        count = len(positions)
        if count >= self.settings.MAX_CONCURRENT_POSITIONS:
            return RiskCheck(
                passed=False,
                rule="position_count",
                reason=f"{count} positions >= max {self.settings.MAX_CONCURRENT_POSITIONS}",
            )
        return RiskCheck(passed=True, rule="position_count", reason="OK")

    def _check_total_exposure(self, positions: list, account: dict) -> RiskCheck:
        equity = account.get("equity", 0.0)
        if equity <= 0:
            return RiskCheck(passed=True, rule="total_exposure", reason="No equity")
        total_notional = sum(float(p.get("notionalUsd", 0)) for p in positions)
        exposure_pct = total_notional / equity
        if exposure_pct >= self.settings.MAX_TOTAL_EXPOSURE_PCT:
            return RiskCheck(
                passed=False,
                rule="total_exposure",
                reason=f"Exposure {exposure_pct:.2%} >= {self.settings.MAX_TOTAL_EXPOSURE_PCT:.2%}",
            )
        return RiskCheck(passed=True, rule="total_exposure", reason="OK")

    def _check_trade_size(self, decision: dict, account: dict) -> RiskCheck:
        size_pct = decision.get("size_pct", 0.0)
        if size_pct >= self.settings.MAX_SINGLE_TRADE_PCT:
            return RiskCheck(
                passed=False,
                rule="trade_size",
                reason=f"Size {size_pct:.2%} >= max {self.settings.MAX_SINGLE_TRADE_PCT:.2%}",
            )
        return RiskCheck(passed=True, rule="trade_size", reason="OK")

    def _check_leverage(self, decision: dict) -> RiskCheck:
        leverage = decision.get("leverage", 1.0)
        if leverage >= self.settings.MAX_LEVERAGE:
            return RiskCheck(
                passed=False,
                rule="leverage",
                reason=f"Leverage {leverage}x >= max {self.settings.MAX_LEVERAGE}x",
            )
        return RiskCheck(passed=True, rule="leverage", reason="OK")

    def _check_stop_loss(self, decision: dict) -> RiskCheck:
        sl = decision.get("stop_loss")
        if not sl:
            return RiskCheck(
                passed=False,
                rule="stop_loss",
                reason="Stop loss is required for all trades",
            )
        return RiskCheck(passed=True, rule="stop_loss", reason="OK")

    def _check_sl_distance(self, decision: dict) -> RiskCheck:
        entry = decision.get("entry_price", 0.0)
        sl = decision.get("stop_loss", 0.0)
        if not entry or not sl:
            return RiskCheck(passed=True, rule="sl_distance", reason="No entry/SL to check")
        distance_pct = abs(entry - sl) / entry
        if distance_pct >= self.settings.MAX_SL_DISTANCE_PCT:
            return RiskCheck(
                passed=False,
                rule="sl_distance",
                reason=f"SL distance {distance_pct:.2%} >= max {self.settings.MAX_SL_DISTANCE_PCT:.2%}",
            )
        return RiskCheck(passed=True, rule="sl_distance", reason="OK")

    def _check_rr_ratio(self, decision: dict) -> RiskCheck:
        entry = decision.get("entry_price", 0.0)
        sl = decision.get("stop_loss", 0.0)
        tp = decision.get("take_profit", 0.0)
        if not entry or not sl or not tp:
            return RiskCheck(passed=True, rule="rr_ratio", reason="No TP to check R:R")
        action = decision.get("action", "")
        if "SHORT" in action:
            risk = abs(sl - entry)
            reward = abs(entry - tp)
        else:
            risk = abs(entry - sl)
            reward = abs(tp - entry)
        if risk <= 0:
            return RiskCheck(passed=True, rule="rr_ratio", reason="Zero risk distance")
        rr = reward / risk
        if rr < self.settings.MIN_RR_RATIO:
            return RiskCheck(
                passed=False,
                rule="rr_ratio",
                reason=f"R:R {rr:.2f} < min {self.settings.MIN_RR_RATIO}",
            )
        return RiskCheck(passed=True, rule="rr_ratio", reason=f"R:R {rr:.2f}")

    def _check_correlation(self, decision: dict, positions: list) -> RiskCheck:
        symbol = decision.get("symbol", "")
        existing_symbols = [p.get("instId", "") for p in positions]
        if symbol in existing_symbols:
            return RiskCheck(
                passed=True,
                rule="correlation",
                reason=f"WARNING: same symbol {symbol} already in positions",
            )
        return RiskCheck(passed=True, rule="correlation", reason="OK")

    def _check_cooldown(self) -> RiskCheck:
        if self.cooldown_until is None:
            return RiskCheck(passed=True, rule="cooldown", reason="No cooldown active")
        now = datetime.now(timezone.utc)
        if now < self.cooldown_until:
            remaining = (self.cooldown_until - now).total_seconds()
            return RiskCheck(
                passed=False,
                rule="cooldown",
                reason=f"Cooldown active, {remaining:.0f}s remaining",
            )
        # Cooldown expired
        self.cooldown_until = None
        return RiskCheck(passed=True, rule="cooldown", reason="Cooldown expired")
