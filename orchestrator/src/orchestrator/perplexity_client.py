"""Perplexity sonar-pro API wrapper."""

from __future__ import annotations

import json

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from orchestrator.config import Settings
from orchestrator.db.repository import ResearchCacheRepository
from orchestrator.models.research import ResearchResult

logger = structlog.get_logger()

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

RESEARCH_SYSTEM_PROMPT = """You are a crypto market research analyst.
Provide concise, factual analysis. Include:
1. Key facts & data points
2. Market sentiment assessment (bullish/bearish/neutral)
3. Potential impact on BTC/ETH price (high/medium/low)
4. Time horizon of impact (immediate/short/medium term)
5. Sources cited
Respond in structured JSON format."""


class PerplexityClient:
    def __init__(self, settings: Settings, cache_repo: ResearchCacheRepository) -> None:
        self.settings = settings
        self.cache_repo = cache_repo

    async def research(self, query: str) -> ResearchResult:
        """Call Perplexity sonar-pro with 1-hour cache."""
        # Check cache first
        cached = await self._check_cache(query)
        if cached is not None:
            logger.info("perplexity_cache_hit", query=query[:50])
            return cached

        # Call API
        raw = await self._call_api(query)
        if not raw:
            return ResearchResult(query=query)

        # Build result
        result = ResearchResult(
            query=query,
            summary=raw.get("summary", ""),
            sentiment=raw.get("sentiment", "neutral"),
            impact_level=raw.get("impact_level", "low"),
            time_horizon=raw.get("time_horizon", "medium"),
            key_points=raw.get("key_points", []),
            trading_implication=raw.get("trading_implication", ""),
            confidence=raw.get("confidence", 0.0),
            sources=raw.get("sources", []),
        )

        # Save to cache
        await self._save_cache(query, result)
        return result

    async def _call_api(self, query: str) -> dict:
        """Send POST to Perplexity API, parse response content as JSON."""
        try:
            raw = await self._call_api_with_retry(query)
            content = raw["choices"][0]["message"]["content"]

            # Try to parse content as JSON
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Try extracting JSON from text
                try:
                    start = content.index("{")
                    end = content.rindex("}") + 1
                    return json.loads(content[start:end])
                except (ValueError, json.JSONDecodeError):
                    logger.warning("perplexity_parse_error", content=content[:200])
                    return {}
        except Exception as e:
            logger.warning("perplexity_api_error", error=str(e))
            return {}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
    async def _call_api_with_retry(self, query: str) -> dict:
        """Low-level HTTP POST with retry on transient errors."""
        async with httpx.AsyncClient() as http:
            response = await http.post(
                PERPLEXITY_API_URL,
                headers={
                    "Authorization": f"Bearer {self.settings.PERPLEXITY_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.PERPLEXITY_MODEL,
                    "messages": [
                        {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
                        {"role": "user", "content": query},
                    ],
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def _check_cache(self, query: str) -> ResearchResult | None:
        """Check cache for recent result within TTL."""
        cached = await self.cache_repo.get_cached(query, ttl_seconds=3600)
        if cached is None:
            return None
        return ResearchResult.model_validate(cached)

    async def _save_cache(self, query: str, result: ResearchResult) -> None:
        """Save research result to cache."""
        await self.cache_repo.save(query, result.model_dump(mode="json"))
