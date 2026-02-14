"""Unit tests for PerplexityClient — httpx API wrapper with cache."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.config import Settings
from orchestrator.models.research import ResearchResult
from orchestrator.perplexity_client import PerplexityClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings():
    return Settings(
        PERPLEXITY_API_KEY="test-pplx-key",
        PERPLEXITY_MODEL="sonar-pro",
    )


@pytest.fixture
def mock_cache_repo():
    repo = AsyncMock()
    repo.get_cached = AsyncMock(return_value=None)
    repo.save = AsyncMock(return_value=1)
    return repo


@pytest.fixture
def client(settings, mock_cache_repo):
    return PerplexityClient(settings=settings, cache_repo=mock_cache_repo)


@pytest.fixture
def valid_api_response():
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "summary": "Fed signals rate pause, bullish for crypto.",
                            "sentiment": "bullish",
                            "impact_level": "high",
                            "time_horizon": "short",
                            "key_points": ["Rate pause likely", "Institutional inflows up"],
                            "trading_implication": "Bullish bias for BTC in short term",
                            "confidence": 0.8,
                            "sources": ["Reuters", "Bloomberg"],
                        }
                    )
                }
            }
        ]
    }


# ---------------------------------------------------------------------------
# _check_cache()
# ---------------------------------------------------------------------------


class TestCheckCache:
    async def test_returns_none_on_miss(self, client, mock_cache_repo):
        """Should return None when cache has no entry."""
        mock_cache_repo.get_cached.return_value = None
        result = await client._check_cache("BTC analysis")
        assert result is None

    async def test_returns_result_on_hit(self, client, mock_cache_repo):
        """Should return ResearchResult when cache has valid entry."""
        cached_data = {
            "summary": "Cached result",
            "sentiment": "neutral",
            "impact_level": "low",
            "time_horizon": "medium",
            "key_points": [],
            "trading_implication": "",
            "confidence": 0.5,
            "sources": [],
        }
        mock_cache_repo.get_cached.return_value = cached_data
        result = await client._check_cache("BTC analysis")
        assert isinstance(result, ResearchResult)
        assert result.summary == "Cached result"

    async def test_cache_called_with_query(self, client, mock_cache_repo):
        """Should call cache_repo.get_cached with the query and TTL."""
        await client._check_cache("test query")
        mock_cache_repo.get_cached.assert_awaited_once_with("test query", ttl_seconds=3600)


# ---------------------------------------------------------------------------
# _save_cache()
# ---------------------------------------------------------------------------


class TestSaveCache:
    async def test_saves_to_cache(self, client, mock_cache_repo):
        """Should save result to cache repo."""
        result = ResearchResult(summary="Test", query="BTC analysis")
        await client._save_cache("BTC analysis", result)
        mock_cache_repo.save.assert_awaited_once()
        call_args = mock_cache_repo.save.call_args
        assert call_args[0][0] == "BTC analysis"


# ---------------------------------------------------------------------------
# _call_api()
# ---------------------------------------------------------------------------


class TestCallApi:
    async def test_returns_parsed_dict(self, client, valid_api_response):
        """Should return parsed response dict from Perplexity API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = valid_api_response
        mock_response.raise_for_status = MagicMock()

        with patch("orchestrator.perplexity_client.httpx.AsyncClient") as MockHttpx:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockHttpx.return_value = mock_http

            result = await client._call_api("BTC analysis query")

        assert isinstance(result, dict)
        assert "summary" in result

    async def test_api_error_returns_empty(self, client):
        """Should return empty dict on API error."""
        with patch("orchestrator.perplexity_client.httpx.AsyncClient") as MockHttpx:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(side_effect=Exception("Connection error"))
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockHttpx.return_value = mock_http

            result = await client._call_api("query")

        assert result == {}

    async def test_sends_correct_model(self, client, valid_api_response):
        """Should send request with correct model."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = valid_api_response
        mock_response.raise_for_status = MagicMock()

        with patch("orchestrator.perplexity_client.httpx.AsyncClient") as MockHttpx:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockHttpx.return_value = mock_http

            await client._call_api("query")

            call_kwargs = mock_http.post.call_args
            body = (
                call_kwargs[1].get("json") or call_kwargs[0][1]
                if len(call_kwargs[0]) > 1
                else call_kwargs[1]["json"]
            )
            assert body["model"] == "sonar-pro"


# ---------------------------------------------------------------------------
# research() — full flow
# ---------------------------------------------------------------------------


class TestResearch:
    async def test_returns_research_result(self, client, valid_api_response, mock_cache_repo):
        """research() should return ResearchResult from API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = valid_api_response
        mock_response.raise_for_status = MagicMock()

        with patch("orchestrator.perplexity_client.httpx.AsyncClient") as MockHttpx:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockHttpx.return_value = mock_http

            result = await client.research("BTC market analysis")

        assert isinstance(result, ResearchResult)
        assert result.summary != ""
        assert result.sentiment == "bullish"

    async def test_returns_cached_on_hit(self, client, mock_cache_repo):
        """research() should return cached result without calling API."""
        cached_data = {
            "summary": "Cached",
            "sentiment": "neutral",
            "impact_level": "low",
            "time_horizon": "medium",
            "key_points": [],
            "trading_implication": "",
            "confidence": 0.5,
            "sources": [],
        }
        mock_cache_repo.get_cached.return_value = cached_data

        with patch("orchestrator.perplexity_client.httpx.AsyncClient") as MockHttpx:
            mock_http = AsyncMock()
            MockHttpx.return_value = mock_http

            result = await client.research("BTC analysis")

        assert result.summary == "Cached"
        # API should NOT have been called
        mock_http.post.assert_not_awaited()

    async def test_saves_to_cache_after_api(self, client, valid_api_response, mock_cache_repo):
        """research() should save result to cache after successful API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = valid_api_response
        mock_response.raise_for_status = MagicMock()

        with patch("orchestrator.perplexity_client.httpx.AsyncClient") as MockHttpx:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockHttpx.return_value = mock_http

            await client.research("BTC analysis")

        mock_cache_repo.save.assert_awaited_once()

    async def test_api_error_returns_empty_result(self, client, mock_cache_repo):
        """research() should return empty ResearchResult on API error."""
        with patch("orchestrator.perplexity_client.httpx.AsyncClient") as MockHttpx:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(side_effect=Exception("API down"))
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockHttpx.return_value = mock_http

            result = await client.research("query")

        assert isinstance(result, ResearchResult)
        assert result.summary == ""

    async def test_malformed_api_response(self, client, mock_cache_repo):
        """research() should handle malformed API response gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": "not json"}}]}
        mock_response.raise_for_status = MagicMock()

        with patch("orchestrator.perplexity_client.httpx.AsyncClient") as MockHttpx:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockHttpx.return_value = mock_http

            result = await client.research("query")

        assert isinstance(result, ResearchResult)
