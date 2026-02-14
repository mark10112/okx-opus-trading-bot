"""Unit tests for OpusClient — Anthropic AsyncClient wrapper for Opus 4.6."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.config import Settings
from orchestrator.models.decision import AnalysisResult, Decision, OpusDecision
from orchestrator.models.reflection import DeepReflectionResult, TradeReview
from orchestrator.opus_client import OpusClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings():
    return Settings(
        ANTHROPIC_API_KEY="test-key",
        OPUS_MODEL="claude-opus-4-6",
        OPUS_MAX_TOKENS=4096,
        MAX_OPUS_TIMEOUT_SECONDS=30,
    )


@pytest.fixture
def client(settings):
    return OpusClient(settings=settings)


@pytest.fixture
def valid_decision_json():
    return json.dumps({
        "analysis": {
            "market_regime": "trending_up",
            "bias": "bullish",
            "key_observations": ["EMA alignment bullish", "RSI healthy"],
            "risk_factors": ["Funding rate elevated"],
        },
        "decision": {
            "action": "OPEN_LONG",
            "symbol": "BTC-USDT-SWAP",
            "size_pct": 0.03,
            "entry_price": 60000.0,
            "stop_loss": 58500.0,
            "take_profit": 63000.0,
            "order_type": "market",
            "limit_price": None,
        },
        "confidence": 0.75,
        "strategy_used": "momentum",
        "reasoning": "Strong trend with healthy pullback to EMA20 support.",
    })


@pytest.fixture
def valid_review_json():
    return json.dumps({
        "outcome": "win",
        "execution_quality": "good",
        "entry_timing": "good",
        "exit_timing": "early",
        "what_went_right": ["Correct trend identification", "Good entry timing"],
        "what_went_wrong": ["Exited too early, missed 30% of the move"],
        "lesson": "Hold winners longer when trend is strong",
        "should_update_playbook": True,
        "playbook_suggestion": "Add trailing stop rule for trending markets",
    })


@pytest.fixture
def valid_deep_reflection_json():
    return json.dumps({
        "updated_playbook": {
            "version": 2,
            "market_regime_rules": {
                "trending_up": {
                    "preferred_strategies": ["momentum", "breakout"],
                    "avoid_strategies": ["mean_reversion"],
                    "max_position_pct": 0.05,
                    "preferred_timeframe": "1H",
                },
            },
            "strategy_definitions": {
                "momentum": {
                    "entry": "EMA20 > EMA50 > EMA200",
                    "exit": "Trailing stop or RSI > 80",
                    "filters": [],
                    "historical_winrate": 0.67,
                    "avg_rr": 2.1,
                },
            },
            "lessons_learned": [
                {
                    "id": "L1",
                    "date": "2026-02-15",
                    "lesson": "Hold winners longer",
                    "evidence": "3 trades exited early",
                    "impact": "high",
                },
            ],
            "confidence_calibration": {},
            "time_filters": {"avoid_hours_utc": [], "preferred_hours_utc": []},
        },
        "pattern_insights": ["Momentum trades perform best in trending_up regime"],
        "bias_findings": ["Tendency to exit winners too early"],
        "discipline_score": 80,
        "summary": "Overall good performance with room for improvement in exit timing.",
    })


# ---------------------------------------------------------------------------
# _parse_decision()
# ---------------------------------------------------------------------------


class TestParseDecision:
    def test_valid_json(self, client, valid_decision_json):
        result = client._parse_decision(valid_decision_json)
        assert isinstance(result, OpusDecision)
        assert result.decision.action == "OPEN_LONG"
        assert result.confidence == 0.75
        assert result.strategy_used == "momentum"

    def test_valid_json_hold(self, client):
        text = json.dumps({
            "analysis": {"market_regime": "ranging", "bias": "neutral"},
            "decision": {"action": "HOLD"},
            "confidence": 0.0,
            "strategy_used": "",
            "reasoning": "No clear setup",
        })
        result = client._parse_decision(text)
        assert result.decision.action == "HOLD"

    def test_malformed_json_returns_hold(self, client):
        """Malformed JSON should return default HOLD decision."""
        result = client._parse_decision("This is not JSON")
        assert isinstance(result, OpusDecision)
        assert result.decision.action == "HOLD"
        assert result.confidence == 0.0

    def test_partial_json_returns_hold(self, client):
        """Incomplete JSON should return default HOLD."""
        result = client._parse_decision('{"analysis": {"market_regime": "trending_up"')
        assert result.decision.action == "HOLD"

    def test_missing_decision_field(self, client):
        """Missing 'decision' field should default to HOLD."""
        text = json.dumps({"analysis": {}, "confidence": 0.5})
        result = client._parse_decision(text)
        assert result.decision.action == "HOLD"

    def test_json_with_extra_text(self, client, valid_decision_json):
        """Should extract JSON from surrounding text."""
        text = f"Here is my analysis:\n{valid_decision_json}\nEnd of analysis."
        result = client._parse_decision(text)
        assert result.decision.action == "OPEN_LONG"


# ---------------------------------------------------------------------------
# _parse_review()
# ---------------------------------------------------------------------------


class TestParseReview:
    def test_valid_json(self, client, valid_review_json):
        result = client._parse_review(valid_review_json)
        assert isinstance(result, TradeReview)
        assert result.outcome == "win"
        assert result.execution_quality == "good"
        assert result.should_update_playbook is True

    def test_malformed_json_returns_empty(self, client):
        """Malformed JSON should return empty TradeReview."""
        result = client._parse_review("not json")
        assert isinstance(result, TradeReview)
        assert result.outcome == ""
        assert result.lesson == ""

    def test_partial_fields(self, client):
        """Partial fields should fill defaults."""
        text = json.dumps({"outcome": "loss", "lesson": "Don't chase"})
        result = client._parse_review(text)
        assert result.outcome == "loss"
        assert result.lesson == "Don't chase"
        assert result.execution_quality == ""


# ---------------------------------------------------------------------------
# _parse_deep_reflection()
# ---------------------------------------------------------------------------


class TestParseDeepReflection:
    def test_valid_json(self, client, valid_deep_reflection_json):
        result = client._parse_deep_reflection(valid_deep_reflection_json)
        assert isinstance(result, DeepReflectionResult)
        assert result.discipline_score == 80
        assert len(result.pattern_insights) > 0
        assert len(result.bias_findings) > 0

    def test_malformed_json_returns_empty(self, client):
        """Malformed JSON should return empty DeepReflectionResult."""
        result = client._parse_deep_reflection("not json")
        assert isinstance(result, DeepReflectionResult)
        assert result.summary == ""
        assert result.discipline_score == 0

    def test_partial_fields(self, client):
        """Partial fields should fill defaults."""
        text = json.dumps({"summary": "Good progress", "discipline_score": 70})
        result = client._parse_deep_reflection(text)
        assert result.summary == "Good progress"
        assert result.discipline_score == 70


# ---------------------------------------------------------------------------
# _call() — mock AsyncAnthropic
# ---------------------------------------------------------------------------


class TestCall:
    async def test_returns_text(self, client):
        """_call() should return response text."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="response text")]

        with patch("orchestrator.opus_client.AsyncAnthropic") as MockClient:
            mock_api = AsyncMock()
            mock_api.messages.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_api

            result = await client._call("system prompt", "user prompt")

        assert result == "response text"

    async def test_timeout_returns_empty(self, client):
        """_call() should return empty string on timeout."""
        with patch("orchestrator.opus_client.AsyncAnthropic") as MockClient:
            mock_api = AsyncMock()
            mock_api.messages.create = AsyncMock(side_effect=asyncio.TimeoutError())
            MockClient.return_value = mock_api

            result = await client._call("system", "user")

        assert result == ""

    async def test_api_error_returns_empty(self, client):
        """_call() should return empty string on API error."""
        with patch("orchestrator.opus_client.AsyncAnthropic") as MockClient:
            mock_api = AsyncMock()
            mock_api.messages.create = AsyncMock(side_effect=Exception("API Error"))
            MockClient.return_value = mock_api

            result = await client._call("system", "user")

        assert result == ""

    async def test_uses_correct_model(self, client):
        """_call() should use the configured model."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]

        with patch("orchestrator.opus_client.AsyncAnthropic") as MockClient:
            mock_api = AsyncMock()
            mock_api.messages.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_api

            await client._call("system", "user", temperature=0.2)

            call_kwargs = mock_api.messages.create.call_args[1]
            assert call_kwargs["model"] == "claude-opus-4-6"
            assert call_kwargs["max_tokens"] == 4096
            assert call_kwargs["temperature"] == 0.2


# ---------------------------------------------------------------------------
# analyze() — full flow
# ---------------------------------------------------------------------------


class TestAnalyze:
    async def test_returns_opus_decision(self, client, valid_decision_json):
        """analyze() should return OpusDecision from mocked API."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=valid_decision_json)]

        with patch("orchestrator.opus_client.AsyncAnthropic") as MockClient:
            mock_api = AsyncMock()
            mock_api.messages.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_api

            result = await client.analyze("analysis prompt here")

        assert isinstance(result, OpusDecision)
        assert result.decision.action == "OPEN_LONG"

    async def test_timeout_returns_hold(self, client):
        """analyze() should return HOLD on timeout."""
        with patch("orchestrator.opus_client.AsyncAnthropic") as MockClient:
            mock_api = AsyncMock()
            mock_api.messages.create = AsyncMock(side_effect=asyncio.TimeoutError())
            MockClient.return_value = mock_api

            result = await client.analyze("prompt")

        assert result.decision.action == "HOLD"

    async def test_uses_temperature_02(self, client, valid_decision_json):
        """analyze() should use temperature=0.2."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=valid_decision_json)]

        with patch("orchestrator.opus_client.AsyncAnthropic") as MockClient:
            mock_api = AsyncMock()
            mock_api.messages.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_api

            await client.analyze("prompt")

            call_kwargs = mock_api.messages.create.call_args[1]
            assert call_kwargs["temperature"] == 0.2


# ---------------------------------------------------------------------------
# reflect_trade() — full flow
# ---------------------------------------------------------------------------


class TestReflectTrade:
    async def test_returns_trade_review(self, client, valid_review_json):
        """reflect_trade() should return TradeReview."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=valid_review_json)]

        with patch("orchestrator.opus_client.AsyncAnthropic") as MockClient:
            mock_api = AsyncMock()
            mock_api.messages.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_api

            result = await client.reflect_trade("post-trade prompt")

        assert isinstance(result, TradeReview)
        assert result.outcome == "win"

    async def test_uses_temperature_03(self, client, valid_review_json):
        """reflect_trade() should use temperature=0.3."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=valid_review_json)]

        with patch("orchestrator.opus_client.AsyncAnthropic") as MockClient:
            mock_api = AsyncMock()
            mock_api.messages.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_api

            await client.reflect_trade("prompt")

            call_kwargs = mock_api.messages.create.call_args[1]
            assert call_kwargs["temperature"] == 0.3


# ---------------------------------------------------------------------------
# deep_reflect() — full flow
# ---------------------------------------------------------------------------


class TestDeepReflect:
    async def test_returns_deep_reflection_result(self, client, valid_deep_reflection_json):
        """deep_reflect() should return DeepReflectionResult."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=valid_deep_reflection_json)]

        with patch("orchestrator.opus_client.AsyncAnthropic") as MockClient:
            mock_api = AsyncMock()
            mock_api.messages.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_api

            result = await client.deep_reflect("deep reflection prompt")

        assert isinstance(result, DeepReflectionResult)
        assert result.discipline_score == 80

    async def test_uses_temperature_03(self, client, valid_deep_reflection_json):
        """deep_reflect() should use temperature=0.3."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=valid_deep_reflection_json)]

        with patch("orchestrator.opus_client.AsyncAnthropic") as MockClient:
            mock_api = AsyncMock()
            mock_api.messages.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_api

            await client.deep_reflect("prompt")

            call_kwargs = mock_api.messages.create.call_args[1]
            assert call_kwargs["temperature"] == 0.3

    async def test_error_returns_empty_result(self, client):
        """deep_reflect() should return empty result on error."""
        with patch("orchestrator.opus_client.AsyncAnthropic") as MockClient:
            mock_api = AsyncMock()
            mock_api.messages.create = AsyncMock(side_effect=Exception("API Error"))
            MockClient.return_value = mock_api

            result = await client.deep_reflect("prompt")

        assert isinstance(result, DeepReflectionResult)
        assert result.summary == ""
