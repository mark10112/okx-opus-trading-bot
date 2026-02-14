"""Tests for retry/backoff on AI client API calls."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.config import Settings


def _make_settings(**overrides) -> Settings:
    defaults = {"ANTHROPIC_API_KEY": "test-key", "PERPLEXITY_API_KEY": "test-key"}
    defaults.update(overrides)
    return Settings(**defaults)


class TestHaikuScreenerRetry:
    """Test HaikuScreener retries on transient API errors."""

    @pytest.mark.asyncio
    async def test_screen_retries_on_api_error(self):
        """screen() retries via _call_api tenacity and succeeds on 3rd attempt."""
        from orchestrator.haiku_screener import HaikuScreener

        settings = _make_settings()
        screener = HaikuScreener(settings)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"signal": true, "reason": "test"}')]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)

        with patch("orchestrator.haiku_screener.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(
                side_effect=[
                    Exception("API error"),
                    Exception("API error"),
                    mock_response,
                ]
            )

            result = await screener.screen({"ticker": {}})
            assert result.signal is True
            assert mock_client.messages.create.call_count == 3

    @pytest.mark.asyncio
    async def test_screen_returns_default_after_max_retries(self):
        """screen() returns fail-open default after _call_api exhausts retries."""
        from orchestrator.haiku_screener import HaikuScreener

        settings = _make_settings()
        screener = HaikuScreener(settings)

        with patch("orchestrator.haiku_screener.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(
                side_effect=Exception("persistent error")
            )

            result = await screener.screen({"ticker": {}})
            # Fail-open: signal=True
            assert result.signal is True
            assert mock_client.messages.create.call_count == 3

    @pytest.mark.asyncio
    async def test_call_api_retries_with_tenacity(self):
        """_call_api uses tenacity to retry 3 times."""
        from orchestrator.haiku_screener import HaikuScreener

        settings = _make_settings()
        screener = HaikuScreener(settings)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"signal": true, "reason": "ok"}')]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)

        with patch("orchestrator.haiku_screener.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(
                side_effect=[
                    Exception("API error"),
                    Exception("API error"),
                    mock_response,
                ]
            )

            result = await screener._call_api("test prompt")
            assert result == mock_response
            assert mock_client.messages.create.call_count == 3

    @pytest.mark.asyncio
    async def test_call_api_raises_after_max_retries(self):
        """_call_api raises after exhausting 3 retries."""
        from orchestrator.haiku_screener import HaikuScreener

        settings = _make_settings()
        screener = HaikuScreener(settings)

        with patch("orchestrator.haiku_screener.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(
                side_effect=Exception("persistent error")
            )

            with pytest.raises(Exception, match="persistent error"):
                await screener._call_api("test prompt")
            assert mock_client.messages.create.call_count == 3


class TestOpusClientRetry:
    """Test OpusClient retries on transient API errors."""

    @pytest.mark.asyncio
    async def test_call_api_retries_on_api_error(self):
        """_call_api() retries up to 3 times on API errors."""
        from orchestrator.opus_client import OpusClient

        settings = _make_settings()
        client = OpusClient(settings)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"action": "HOLD"}')]

        with patch("orchestrator.opus_client.AsyncAnthropic") as mock_cls:
            mock_api = AsyncMock()
            mock_cls.return_value = mock_api
            mock_api.messages.create = AsyncMock(
                side_effect=[
                    Exception("API error"),
                    Exception("API error"),
                    mock_response,
                ]
            )

            result = await client._call_api("system", "user", 0.2)
            assert result == mock_response
            assert mock_api.messages.create.call_count == 3

    @pytest.mark.asyncio
    async def test_call_no_retry_on_timeout(self):
        """_call() does NOT retry on TimeoutError — returns empty immediately."""
        from orchestrator.opus_client import OpusClient

        settings = _make_settings(MAX_OPUS_TIMEOUT_SECONDS=1)
        client = OpusClient(settings)

        call_count = 0

        async def _fake_call_api(system, user, temperature):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(10)  # Will be cancelled by wait_for timeout

        client._call_api = _fake_call_api

        result = await client._call("system", "user")
        assert result == ""
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_call_returns_empty_after_max_retries(self):
        """_call() returns empty string after _call_api exhausts retries."""
        from orchestrator.opus_client import OpusClient

        settings = _make_settings()
        client = OpusClient(settings)

        with patch("orchestrator.opus_client.AsyncAnthropic") as mock_cls:
            mock_api = AsyncMock()
            mock_cls.return_value = mock_api
            mock_api.messages.create = AsyncMock(
                side_effect=Exception("persistent error")
            )

            result = await client._call("system", "user")
            assert result == ""
            assert mock_api.messages.create.call_count == 3


class TestPerplexityClientRetry:
    """Test PerplexityClient retries on transient API errors."""

    @pytest.mark.asyncio
    async def test_call_api_with_retry_retries_on_error(self):
        """_call_api_with_retry() retries up to 3 times on HTTP errors."""
        from orchestrator.perplexity_client import PerplexityClient

        settings = _make_settings()
        cache_repo = AsyncMock()
        client = PerplexityClient(settings, cache_repo)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"summary": "test"}'}}]
        }

        with patch("orchestrator.perplexity_client.httpx.AsyncClient") as mock_http_cls:
            mock_http = AsyncMock()
            mock_http_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(
                side_effect=[
                    Exception("connection error"),
                    Exception("connection error"),
                    mock_response,
                ]
            )

            result = await client._call_api_with_retry("test query")
            assert result == mock_response.json.return_value
            assert mock_http.post.call_count == 3

    @pytest.mark.asyncio
    async def test_call_api_returns_empty_after_max_retries(self):
        """_call_api() returns empty dict after _call_api_with_retry exhausts retries."""
        from orchestrator.perplexity_client import PerplexityClient

        settings = _make_settings()
        cache_repo = AsyncMock()
        client = PerplexityClient(settings, cache_repo)

        with patch("orchestrator.perplexity_client.httpx.AsyncClient") as mock_http_cls:
            mock_http = AsyncMock()
            mock_http_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(side_effect=Exception("persistent error"))

            result = await client._call_api("test query")
            assert result == {}
            assert mock_http.post.call_count == 3
