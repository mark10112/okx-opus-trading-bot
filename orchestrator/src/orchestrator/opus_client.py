"""Anthropic AsyncClient wrapper for Opus 4.6."""

from __future__ import annotations

import asyncio
import json

import structlog
from anthropic import AsyncAnthropic

from orchestrator.config import Settings
from orchestrator.models.decision import OpusDecision
from orchestrator.models.reflection import DeepReflectionResult, TradeReview

logger = structlog.get_logger()

ANALYSIS_SYSTEM_PROMPT = """You are an expert crypto trading analyst.
Analyze the market data and make a trading decision.
Follow the playbook rules strictly. Only trade when you have high conviction.
Default to HOLD if uncertain. Always include stop loss and take profit.
Respond ONLY with a single JSON object matching the output_format."""

REFLECTION_SYSTEM_PROMPT = """You are a trading performance coach.
Review the completed trade objectively. Identify what went right and wrong.
Be honest and specific. Focus on actionable lessons.
Respond ONLY with a single JSON object matching the output_format."""

DEEP_REFLECTION_SYSTEM_PROMPT = """You are a trading system optimizer.
Analyze the full trading history and current playbook.
Identify patterns, biases, and areas for improvement.
Propose specific, evidence-based playbook updates.
Respond ONLY with a single JSON object matching the output_format."""


class OpusClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def analyze(self, prompt: str) -> OpusDecision:
        """Send full analysis prompt to Opus 4.6. Default HOLD on timeout."""
        text = await self._call(ANALYSIS_SYSTEM_PROMPT, prompt, temperature=0.2)
        return self._parse_decision(text)

    async def reflect_trade(self, prompt: str) -> TradeReview:
        """Post-trade self-reflection."""
        text = await self._call(REFLECTION_SYSTEM_PROMPT, prompt, temperature=0.3)
        return self._parse_review(text)

    async def deep_reflect(self, prompt: str) -> DeepReflectionResult:
        """Periodic deep reflection every 20 trades or 6 hours."""
        text = await self._call(DEEP_REFLECTION_SYSTEM_PROMPT, prompt, temperature=0.3)
        return self._parse_deep_reflection(text)

    async def _call(self, system: str, user: str, temperature: float = 0.2) -> str:
        """Low-level Anthropic API call with timeout."""
        try:
            client = AsyncAnthropic(api_key=self.settings.ANTHROPIC_API_KEY)
            response = await asyncio.wait_for(
                client.messages.create(
                    model=self.settings.OPUS_MODEL,
                    max_tokens=self.settings.OPUS_MAX_TOKENS,
                    temperature=temperature,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                ),
                timeout=self.settings.MAX_OPUS_TIMEOUT_SECONDS,
            )
            text = response.content[0].text
            logger.info("opus_call", model=self.settings.OPUS_MODEL, chars=len(text))
            return text
        except asyncio.TimeoutError:
            logger.warning("opus_timeout", timeout=self.settings.MAX_OPUS_TIMEOUT_SECONDS)
            return ""
        except Exception as e:
            logger.warning("opus_error", error=str(e))
            return ""

    def _parse_decision(self, text: str) -> OpusDecision:
        """Parse JSON response into OpusDecision. Default HOLD on failure."""
        if not text:
            return OpusDecision()

        data = self._extract_json(text)
        if data is None:
            return OpusDecision()

        try:
            return OpusDecision.model_validate(data)
        except Exception:
            logger.warning("opus_parse_decision_error", raw_text=text[:200])
            return OpusDecision()

    def _parse_review(self, text: str) -> TradeReview:
        """Parse JSON response into TradeReview. Empty on failure."""
        if not text:
            return TradeReview()

        data = self._extract_json(text)
        if data is None:
            return TradeReview()

        try:
            return TradeReview.model_validate(data)
        except Exception:
            logger.warning("opus_parse_review_error", raw_text=text[:200])
            return TradeReview()

    def _parse_deep_reflection(self, text: str) -> DeepReflectionResult:
        """Parse JSON response into DeepReflectionResult. Empty on failure."""
        if not text:
            return DeepReflectionResult()

        data = self._extract_json(text)
        if data is None:
            return DeepReflectionResult()

        try:
            return DeepReflectionResult.model_validate(data)
        except Exception:
            logger.warning("opus_parse_deep_reflection_error", raw_text=text[:200])
            return DeepReflectionResult()

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """Try to extract a JSON object from text."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            pass

        return None
