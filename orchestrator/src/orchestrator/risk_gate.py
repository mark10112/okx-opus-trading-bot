"""Hardcoded circuit breakers — Opus CANNOT override these rules."""

from __future__ import annotations

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
        self.cooldown_until = None
        self.peak_equity: float = 0.0
        self.daily_start_equity: float = 0.0

    def validate(
        self, decision: dict, account: dict, positions: list
    ) -> RiskResult:
        """Run all risk checks sequentially. Returns RiskResult."""
        ...

    def update_on_trade_close(self, pnl: float) -> None:
        """Update consecutive_losses counter, peak_equity tracking."""
        ...

    def reset_daily(self) -> None:
        """Reset daily_start_equity at 00:00 UTC."""
        ...

    def _check_daily_loss(self, account: dict) -> RiskCheck:
        ...

    def _check_max_drawdown(self, account: dict) -> RiskCheck:
        ...

    def _check_position_count(self, positions: list) -> RiskCheck:
        ...

    def _check_total_exposure(self, positions: list, account: dict) -> RiskCheck:
        ...

    def _check_trade_size(self, decision: dict, account: dict) -> RiskCheck:
        ...

    def _check_leverage(self, decision: dict) -> RiskCheck:
        ...

    def _check_stop_loss(self, decision: dict) -> RiskCheck:
        ...

    def _check_sl_distance(self, decision: dict) -> RiskCheck:
        ...

    def _check_rr_ratio(self, decision: dict) -> RiskCheck:
        ...

    def _check_correlation(self, decision: dict, positions: list) -> RiskCheck:
        ...

    def _check_cooldown(self) -> RiskCheck:
        ...
