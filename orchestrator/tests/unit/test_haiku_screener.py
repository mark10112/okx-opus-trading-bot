"""Unit tests for HaikuScreener — Haiku 4.5 pre-filter with AsyncAnthropic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.config import Settings
from orchestrator.haiku_screener import HaikuScreener
from orchestrator.models.screen_result import ScreenResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings():
    return Settings(
        ANTHROPIC_API_KEY="test-key",
        HAIKU_MODEL="claude-haiku-4-5-20251001",
        HAIKU_MAX_TOKENS=100,
    )


@pytest.fixture
def screener(settings):
    return HaikuScreener(settings=settings)


@pytest.fixture
def sample_snapshot():
    return {
        "ticker": {"symbol": "BTC-USDT-SWAP", "last": 60000.0},
        "indicators": {
            "1H": {
                "rsi": 55.0,
                "macd": {"line": 100.0, "signal": 80.0, "histogram": 20.0},
                "adx": 30.0,
                "bb_position": "middle",
                "ema_alignment": "bullish",
                "macd_signal": "bullish",
                "atr": 500.0,
            },
        },
        "market_regime": "trending_up",
        "funding_rate": {"current": 0.0001},
        "price_change_1h": 0.015,
        "long_short_ratio": 1.2,
    }


# ---------------------------------------------------------------------------
# _build_prompt()
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def test_returns_string(self, screener, sample_snapshot):
        result = screener._build_prompt(sample_snapshot)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_price(self, screener, sample_snapshot):
        result = screener._build_prompt(sample_snapshot)
        assert "60000" in result

    def test_includes_rsi(self, screener, sample_snapshot):
        result = screener._build_prompt(sample_snapshot)
        assert "55" in result

    def test_includes_regime(self, screener, sample_snapshot):
        result = screener._build_prompt(sample_snapshot)
        assert "trending_up" in result

    def test_includes_adx(self, screener, sample_snapshot):
        result = screener._build_prompt(sample_snapshot)
        assert "30" in result

    def test_empty_indicators(self, screener):
        """Should handle snapshot with no indicators gracefully."""
        snapshot = {
            "ticker": {"symbol": "BTC-USDT-SWAP", "last": 60000.0},
            "indicators": {},
            "market_regime": "ranging",
            "funding_rate": {"current": 0.0},
            "price_change_1h": 0.0,
        }
        result = screener._build_prompt(snapshot)
        assert isinstance(result, str)
        assert "60000" in result


# ---------------------------------------------------------------------------
# _parse_response()
# ---------------------------------------------------------------------------


class TestParseResponse:
    def test_valid_json_signal_true(self, screener):
        text = '{"signal": true, "reason": "Strong breakout with volume"}'
        result = screener._parse_response(text)
        assert isinstance(result, ScreenResult)
        assert result.signal is True
        assert result.reason == "Strong breakout with volume"

    def test_valid_json_signal_false(self, screener):
        text = '{"signal": false, "reason": "Choppy market"}'
        result = screener._parse_response(text)
        assert result.signal is False
        assert result.reason == "Choppy market"

    def test_malformed_json_defaults_signal_true(self, screener):
        """Malformed JSON should default to signal=True (fail-open)."""
        text = "This is not JSON at all"
        result = screener._parse_response(text)
        assert result.signal is True
        assert "parse" in result.reason.lower() or "error" in result.reason.lower() or "malformed" in result.reason.lower()

    def test_missing_signal_field(self, screener):
        """Missing 'signal' field should default to signal=True."""
        text = '{"reason": "some reason"}'
        result = screener._parse_response(text)
        assert result.signal is True

    def test_missing_reason_field(self, screener):
        """Missing 'reason' field should use empty string."""
        text = '{"signal": false}'
        result = screener._parse_response(text)
        assert result.signal is False
        assert result.reason == ""

    def test_json_with_extra_text(self, screener):
        """Should handle JSON embedded in extra text."""
        text = 'Here is my analysis: {"signal": true, "reason": "RSI extreme"}'
        result = screener._parse_response(text)
        # Should still parse or default to True
        assert result.signal is True


# ---------------------------------------------------------------------------
# screen() — mock AsyncAnthropic
# ---------------------------------------------------------------------------


class TestScreen:
    async def test_screen_returns_screen_result(self, screener, sample_snapshot):
        """screen() should return ScreenResult with mocked API."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"signal": true, "reason": "Breakout detected"}')]
        mock_response.usage = MagicMock(input_tokens=50, output_tokens=20)

        with patch("orchestrator.haiku_screener.AsyncAnthropic") as MockClient:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_client

            result = await screener.screen(sample_snapshot)

        assert isinstance(result, ScreenResult)
        assert result.signal is True
        assert result.reason == "Breakout detected"
        assert result.tokens_used == 70

    async def test_screen_signal_false(self, screener, sample_snapshot):
        """screen() should return signal=False when Haiku says no."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"signal": false, "reason": "No setup"}')]
        mock_response.usage = MagicMock(input_tokens=50, output_tokens=15)

        with patch("orchestrator.haiku_screener.AsyncAnthropic") as MockClient:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_client

            result = await screener.screen(sample_snapshot)

        assert result.signal is False

    async def test_screen_api_error_defaults_true(self, screener, sample_snapshot):
        """screen() should default to signal=True on API error."""
        with patch("orchestrator.haiku_screener.AsyncAnthropic") as MockClient:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(side_effect=Exception("API Error"))
            MockClient.return_value = mock_client

            result = await screener.screen(sample_snapshot)

        assert isinstance(result, ScreenResult)
        assert result.signal is True
        assert "error" in result.reason.lower()

    async def test_screen_timeout_defaults_true(self, screener, sample_snapshot):
        """screen() should default to signal=True on timeout."""
        import asyncio

        with patch("orchestrator.haiku_screener.AsyncAnthropic") as MockClient:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(side_effect=asyncio.TimeoutError())
            MockClient.return_value = mock_client

            result = await screener.screen(sample_snapshot)

        assert result.signal is True

    async def test_screen_uses_correct_model(self, screener, sample_snapshot):
        """screen() should call Anthropic with the correct model."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"signal": true, "reason": "ok"}')]
        mock_response.usage = MagicMock(input_tokens=50, output_tokens=10)

        with patch("orchestrator.haiku_screener.AsyncAnthropic") as MockClient:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_client

            await screener.screen(sample_snapshot)

            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
            assert call_kwargs["max_tokens"] == 100

    async def test_screen_latency_tracked(self, screener, sample_snapshot):
        """screen() should track latency in the result."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"signal": true, "reason": "ok"}')]
        mock_response.usage = MagicMock(input_tokens=50, output_tokens=10)

        with patch("orchestrator.haiku_screener.AsyncAnthropic") as MockClient:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_client

            result = await screener.screen(sample_snapshot)

        # Latency should be a non-negative number
        assert hasattr(result, "latency_ms")
        assert result.latency_ms >= 0
