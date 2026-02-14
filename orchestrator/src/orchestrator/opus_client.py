"""Anthropic AsyncClient wrapper for Opus 4.6."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from orchestrator.config import Settings
    from orchestrator.models.decision import OpusDecision
    from orchestrator.models.reflection import DeepReflectionResult, TradeReview

logger = structlog.get_logger()


class OpusClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def analyze(self, prompt: str) -> OpusDecision:
        """Send full analysis prompt to Opus 4.6. Default HOLD on timeout."""
        ...

    async def reflect_trade(
        self, trade: dict, indicators_at_entry: dict, indicators_at_exit: dict
    ) -> TradeReview:
        """Post-trade self-reflection."""
        ...

    async def deep_reflect(
        self, trades: list, playbook: dict, performance: dict
    ) -> DeepReflectionResult:
        """Periodic deep reflection every 20 trades or 6 hours."""
        ...

    async def _call(self, system: str, user: str) -> str:
        """Low-level Anthropic API call with timeout."""
        ...

    def _parse_decision(self, text: str) -> OpusDecision: ...

    def _parse_review(self, text: str) -> TradeReview: ...

    def _parse_deep_reflection(self, text: str) -> DeepReflectionResult: ...
