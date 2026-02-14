"""Tests for retry/backoff on OKX REST API calls."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from indicator_trade.models.order import OrderRequest
from indicator_trade.trade.okx_rest import OKXRestClient


@pytest.fixture
def rest_client() -> OKXRestClient:
    return OKXRestClient(
        api_key="test-key",
        secret_key="test-secret",
        passphrase="test-pass",
        flag="1",
    )


class TestOKXRestRetry:
    """Test OKXRestClient retries on transient API errors for read-only methods."""

    @pytest.mark.asyncio
    async def test_get_ticker_retries_on_error(self, rest_client: OKXRestClient):
        """get_ticker() retries up to 3 times on transient errors."""
        good_result = {
            "code": "0",
            "data": [{"last": "100", "bidPx": "99", "askPx": "101", "vol24h": "5000", "sodUtc8": "1"}],
        }
        call_count = 0

        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("connection error")
            return good_result

        rest_client._market_api.get_ticker = _side_effect

        result = await rest_client.get_ticker("BTC-USDT-SWAP")
        assert result.last == 100.0
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_get_balance_retries_on_error(self, rest_client: OKXRestClient):
        """get_balance() retries up to 3 times on transient errors."""
        good_result = {
            "code": "0",
            "data": [{"totalEq": "10000", "details": [{"ccy": "USDT", "availBal": "5000"}]}],
        }
        call_count = 0

        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("timeout")
            return good_result

        rest_client._account_api.get_account_balance = _side_effect

        result = await rest_client.get_balance()
        assert result.equity == 10000.0
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_get_ticker_returns_default_after_max_retries(self, rest_client: OKXRestClient):
        """get_ticker() returns default Ticker after exhausting retries."""
        rest_client._market_api.get_ticker = MagicMock(side_effect=Exception("persistent error"))

        result = await rest_client.get_ticker("BTC-USDT-SWAP")
        assert result.last == 0
        assert rest_client._market_api.get_ticker.call_count == 3

    @pytest.mark.asyncio
    async def test_get_candles_retries_on_error(self, rest_client: OKXRestClient):
        """get_candles() retries up to 3 times on transient errors."""
        good_result = {
            "code": "0",
            "data": [
                ["1700000000000", "100", "105", "95", "102", "1000", "1000000", "1000000", "1"],
            ],
        }
        call_count = 0

        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("error")
            return good_result

        rest_client._market_api.get_candlesticks = _side_effect

        result = await rest_client.get_candles("BTC-USDT-SWAP", "1H", limit=1)
        assert len(result) == 1
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_place_order_no_retry(self, rest_client: OKXRestClient):
        """place_order() does NOT retry — trade mutations are not idempotent."""
        rest_client._trade_api.place_order = MagicMock(side_effect=Exception("error"))

        request = OrderRequest(
            action="OPEN_LONG",
            symbol="BTC-USDT-SWAP",
            side="buy",
            pos_side="long",
            order_type="market",
            size="1",
        )
        result = await rest_client.place_order(request)
        assert result.success is False
        # Should NOT retry trade mutations
        assert rest_client._trade_api.place_order.call_count == 1
