"""Haiku 4.5 pre-filter for market screening."""

from __future__ import annotations

import json
import time

import structlog
from anthropic import AsyncAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential

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
        prompt = self._build_prompt(snapshot)
        start = time.monotonic()
        try:
            response = await self._call_api(prompt)
            elapsed_ms = (time.monotonic() - start) * 1000
            text = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens
            result = self._parse_response(text)
            result.tokens_used = tokens
            result.latency_ms = elapsed_ms
            logger.info(
                "haiku_screen",
                signal=result.signal,
                reason=result.reason,
                tokens=tokens,
                latency_ms=round(elapsed_ms, 1),
            )
            return result
        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.warning("haiku_screen_error", error=str(e))
            return ScreenResult(
                signal=True,
                reason=f"Screener error: {e}",
                tokens_used=0,
                latency_ms=elapsed_ms,
            )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
    async def _call_api(self, prompt: str):
        """Low-level Anthropic API call with retry."""
        client = AsyncAnthropic(api_key=self.settings.ANTHROPIC_API_KEY)
        return await client.messages.create(
            model=self.settings.HAIKU_MODEL,
            max_tokens=self.settings.HAIKU_MAX_TOKENS,
            system=SCREENER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

    def _build_prompt(self, snapshot: dict) -> str:
        """Build compact prompt from snapshot."""
        ticker = snapshot.get("ticker", {})
        regime = snapshot.get("market_regime", "unknown")
        funding = snapshot.get("funding_rate", {})
        funding_rate = funding.get("current", 0.0) if isinstance(funding, dict) else 0.0
        price_change = snapshot.get("price_change_1h", 0.0)
        ls_ratio = snapshot.get("long_short_ratio", 1.0)

        parts = []
        parts.append(f"Symbol: {ticker.get('symbol', 'N/A')}")
        parts.append(f"Price: {ticker.get('last', 0.0)}")
        parts.append(f"Regime: {regime}")
        parts.append(f"1H Change: {price_change:.4f}")
        parts.append(f"Funding: {funding_rate:.6f}")
        parts.append(f"L/S Ratio: {ls_ratio:.2f}")

        indicators = snapshot.get("indicators", {})
        for tf, ind in indicators.items():
            parts.append(
                f"[{tf}] RSI:{ind.get('rsi', 'N/A')} ADX:{ind.get('adx', 'N/A')} BB:{ind.get('bb_position', 'N/A')} EMA:{ind.get('ema_alignment', 'N/A')} MACD:{ind.get('macd_signal', 'N/A')}"
            )

        return "\n".join(parts)

    def _parse_response(self, text: str) -> ScreenResult:
        """Parse JSON response from Haiku."""
        try:
            # Try direct parse first
            data = json.loads(text)
            return ScreenResult(
                signal=data.get("signal", True),
                reason=data.get("reason", ""),
            )
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from text
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            data = json.loads(text[start:end])
            return ScreenResult(
                signal=data.get("signal", True),
                reason=data.get("reason", ""),
            )
        except (ValueError, json.JSONDecodeError):
            pass

        # Default to signal=True on parse failure (fail-open)
        logger.warning("haiku_parse_error", raw_text=text[:200])
        return ScreenResult(
            signal=True,
            reason="Parse error: malformed response",
        )
