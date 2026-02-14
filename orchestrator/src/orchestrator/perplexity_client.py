"""Perplexity sonar-pro API wrapper."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from orchestrator.config import Settings
    from orchestrator.models.research import ResearchResult

logger = structlog.get_logger()

RESEARCH_SYSTEM_PROMPT = """You are a crypto market research analyst.
Provide concise, factual analysis. Include:
1. Key facts & data points
2. Market sentiment assessment (bullish/bearish/neutral)
3. Potential impact on BTC/ETH price (high/medium/low)
4. Time horizon of impact (immediate/short/medium term)
5. Sources cited
Respond in structured JSON format."""


class PerplexityClient:
    def __init__(self, settings: Settings, cache_repo: object) -> None:
        self.settings = settings
        self.cache_repo = cache_repo

    async def research(self, query: str) -> ResearchResult:
        """Call Perplexity sonar-pro with 1-hour cache."""
        ...

    async def _call_api(self, query: str) -> dict: ...

    async def _check_cache(self, query: str) -> ResearchResult | None: ...

    async def _save_cache(self, query: str, result: ResearchResult) -> None: ...
