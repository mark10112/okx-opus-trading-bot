"""Haiku 4.5 pre-filter for market screening."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from orchestrator.config import Settings
    from orchestrator.models.screen_result import ScreenResult

logger = structlog.get_logger()

SCREENER_SYSTEM_PROMPT = """You are a quick crypto market screener.
Given a market snapshot, determine if there's an actionable trading setup RIGHT NOW.
Signal = true ONLY if:
- Clear breakout/breakdown with volume
- RSI extreme (<30 or >70) in ranging market
- Strong trend pullback to EMA support
- Significant divergence between indicators
Signal = false if market is choppy, unclear, or already priced in.
Respond ONLY with JSON: {"signal": true/false, "reason": "..."}"""


class HaikuScreener:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def screen(self, snapshot: dict) -> ScreenResult:
        """Call Haiku 4.5 with compact snapshot (~500 tokens input)."""
        ...

    def _build_prompt(self, snapshot: dict) -> str:
        """Build compact prompt from snapshot."""
        ...

    def _parse_response(self, text: str) -> ScreenResult:
        """Parse JSON response from Haiku."""
        ...
