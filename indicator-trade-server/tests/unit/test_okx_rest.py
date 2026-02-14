"""Unit tests for OKX REST client wrapper."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from indicator_trade.models.order import OrderRequest, OrderResult
from indicator_trade.models.position import AccountState, Position
from indicator_trade.trade.okx_rest import OKXRestClient


# --- Fixtures ---


@pytest.fixture
def rest_client() -> OKXRestClient:
    return OKXRestClient(
        api_key="test-key",
        secret_key="test-secret",
        passphrase="test-pass",
        flag="1",
    )


# --- Constructor ---


class TestOKXRestClientInit:
    def test_init_creates_sdk_clients(self, rest_client: OKXRestClient) -> None:
        assert rest_client._trade_api is not None
        assert rest_client._account_api is not None
        assert rest_client._market_api is not None
        assert rest_client._public_api is not None

    def test_init_stores_flag(self, rest_client: OKXRestClient) -> None:
        assert rest_client.flag == "1"


# --- Trade methods ---


class TestPlaceOrder:
    @pytest.mark.asyncio
    async def test_place_order_market_success(self, rest_client: OKXRestClient) -> None:
        rest_client._trade_api = MagicMock()
        rest_client._trade_api.place_order = MagicMock(
            return_value={
                "code": "0",
                "data": [{"ordId": "12345", "sCode": "0", "sMsg": ""}],
            }
        )
        request = OrderRequest(
            action="OPEN_LONG",
            symbol="BTC-USDT-SWAP",
            side="buy",
            pos_side="long",
            order_type="market",
            size="1",
        )
        result = await rest_client.place_order(request)
        assert result.success is True
        assert result.ord_id == "12345"

    @pytest.mark.asyncio
    async def test_place_order_limit_success(self, rest_client: OKXRestClient) -> None:
        rest_client._trade_api = MagicMock()
        rest_client._trade_api.place_order = MagicMock(
            return_value={
                "code": "0",
                "data": [{"ordId": "12346", "sCode": "0", "sMsg": ""}],
            }
        )
        request = OrderRequest(
            action="OPEN_LONG",
            symbol="BTC-USDT-SWAP",
            side="buy",
            pos_side="long",
            order_type="limit",
            size="1",
            limit_price="50000",
        )
        result = await rest_client.place_order(request)
        assert result.success is True
        assert result.ord_id == "12346"

    @pytest.mark.asyncio
    async def test_place_order_api_error(self, rest_client: OKXRestClient) -> None:
        rest_client._trade_api = MagicMock()
        rest_client._trade_api.place_order = MagicMock(
            return_value={
                "code": "1",
                "data": [{"ordId": "", "sCode": "51000", "sMsg": "Parameter error"}],
            }
        )
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
        assert result.error_code == "51000"
        assert result.error_message == "Parameter error"

    @pytest.mark.asyncio
    async def test_place_order_exception(self, rest_client: OKXRestClient) -> None:
        rest_client._trade_api = MagicMock()
        rest_client._trade_api.place_order = MagicMock(side_effect=Exception("Network error"))
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
        assert "Network error" in result.error_message


class TestPlaceAlgoOrder:
    @pytest.mark.asyncio
    async def test_place_algo_order_sl_only(self, rest_client: OKXRestClient) -> None:
        rest_client._trade_api = MagicMock()
        rest_client._trade_api.place_algo_order = MagicMock(
            return_value={
                "code": "0",
                "data": [{"algoId": "algo-1", "sCode": "0", "sMsg": ""}],
            }
        )
        result = await rest_client.place_algo_order(
            instId="BTC-USDT-SWAP",
            tdMode="cross",
            side="sell",
            posSide="long",
            sz="1",
            slTriggerPx="49000",
        )
        assert result["code"] == "0"
        assert result["data"][0]["algoId"] == "algo-1"

    @pytest.mark.asyncio
    async def test_place_algo_order_sl_and_tp(self, rest_client: OKXRestClient) -> None:
        rest_client._trade_api = MagicMock()
        rest_client._trade_api.place_algo_order = MagicMock(
            return_value={
                "code": "0",
                "data": [{"algoId": "algo-2", "sCode": "0", "sMsg": ""}],
            }
        )
        result = await rest_client.place_algo_order(
            instId="BTC-USDT-SWAP",
            tdMode="cross",
            side="sell",
            posSide="long",
            sz="1",
            slTriggerPx="49000",
            tpTriggerPx="55000",
        )
        assert result["code"] == "0"


class TestCancelOrder:
    @pytest.mark.asyncio
    async def test_cancel_order_success(self, rest_client: OKXRestClient) -> None:
        rest_client._trade_api = MagicMock()
        rest_client._trade_api.cancel_order = MagicMock(
            return_value={"code": "0", "data": [{"ordId": "12345", "sCode": "0"}]}
        )
        result = await rest_client.cancel_order("BTC-USDT-SWAP", "12345")
        assert result["code"] == "0"


class TestClosePosition:
    @pytest.mark.asyncio
    async def test_close_position_success(self, rest_client: OKXRestClient) -> None:
        rest_client._trade_api = MagicMock()
        rest_client._trade_api.close_positions = MagicMock(
            return_value={"code": "0", "data": [{"instId": "BTC-USDT-SWAP"}]}
        )
        result = await rest_client.close_position("BTC-USDT-SWAP", "cross", "long")
        assert result["code"] == "0"


# --- Account methods ---


class TestGetBalance:
    @pytest.mark.asyncio
    async def test_get_balance_success(self, rest_client: OKXRestClient) -> None:
        rest_client._account_api = MagicMock()
        rest_client._account_api.get_account_balance = MagicMock(
            return_value={
                "code": "0",
                "data": [
                    {
                        "totalEq": "10000.5",
                        "details": [{"availBal": "8000.0", "ccy": "USDT"}],
                    }
                ],
            }
        )
        account = await rest_client.get_balance()
        assert isinstance(account, AccountState)
        assert account.equity == 10000.5
        assert account.available_balance == 8000.0

    @pytest.mark.asyncio
    async def test_get_balance_empty_response(self, rest_client: OKXRestClient) -> None:
        rest_client._account_api = MagicMock()
        rest_client._account_api.get_account_balance = MagicMock(
            return_value={"code": "0", "data": []}
        )
        account = await rest_client.get_balance()
        assert account.equity == 0.0


class TestGetPositions:
    @pytest.mark.asyncio
    async def test_get_positions_success(self, rest_client: OKXRestClient) -> None:
        rest_client._account_api = MagicMock()
        rest_client._account_api.get_positions = MagicMock(
            return_value={
                "code": "0",
                "data": [
                    {
                        "instId": "BTC-USDT-SWAP",
                        "posSide": "long",
                        "pos": "1",
                        "avgPx": "50000",
                        "upl": "100",
                        "uplRatio": "0.02",
                        "lever": "3",
                        "liqPx": "45000",
                        "margin": "5000",
                        "mgnRatio": "0.1",
                        "uTime": "1700000000000",
                    }
                ],
            }
        )
        positions = await rest_client.get_positions()
        assert len(positions) == 1
        assert positions[0].instId == "BTC-USDT-SWAP"
        assert positions[0].pos == 1.0
        assert positions[0].avgPx == 50000.0

    @pytest.mark.asyncio
    async def test_get_positions_with_instid_filter(self, rest_client: OKXRestClient) -> None:
        rest_client._account_api = MagicMock()
        rest_client._account_api.get_positions = MagicMock(
            return_value={"code": "0", "data": []}
        )
        positions = await rest_client.get_positions(instId="BTC-USDT-SWAP")
        assert positions == []

    @pytest.mark.asyncio
    async def test_get_positions_empty(self, rest_client: OKXRestClient) -> None:
        rest_client._account_api = MagicMock()
        rest_client._account_api.get_positions = MagicMock(
            return_value={"code": "0", "data": []}
        )
        positions = await rest_client.get_positions()
        assert positions == []


class TestSetLeverage:
    @pytest.mark.asyncio
    async def test_set_leverage_success(self, rest_client: OKXRestClient) -> None:
        rest_client._account_api = MagicMock()
        rest_client._account_api.set_leverage = MagicMock(
            return_value={"code": "0", "data": [{"lever": "3"}]}
        )
        result = await rest_client.set_leverage("BTC-USDT-SWAP", "3")
        assert result["code"] == "0"


# --- Market methods ---


class TestGetCandles:
    @pytest.mark.asyncio
    async def test_get_candles_success(self, rest_client: OKXRestClient) -> None:
        rest_client._market_api = MagicMock()
        rest_client._market_api.get_candlesticks = MagicMock(
            return_value={
                "code": "0",
                "data": [
                    ["1700000000000", "50000", "51000", "49000", "50500", "100", "0", "0", "1"],
                    ["1700003600000", "50500", "52000", "50000", "51500", "200", "0", "0", "1"],
                ],
            }
        )
        candles = await rest_client.get_candles("BTC-USDT-SWAP", "1H")
        assert len(candles) == 2
        assert candles[0].symbol == "BTC-USDT-SWAP"
        # reversed: second row becomes first (chronological order)
        assert float(candles[0].close) == 51500.0
        assert float(candles[1].close) == 50500.0

    @pytest.mark.asyncio
    async def test_get_candles_empty(self, rest_client: OKXRestClient) -> None:
        rest_client._market_api = MagicMock()
        rest_client._market_api.get_candlesticks = MagicMock(
            return_value={"code": "0", "data": []}
        )
        candles = await rest_client.get_candles("BTC-USDT-SWAP", "1H")
        assert candles == []


class TestGetTicker:
    @pytest.mark.asyncio
    async def test_get_ticker_success(self, rest_client: OKXRestClient) -> None:
        rest_client._market_api = MagicMock()
        rest_client._market_api.get_ticker = MagicMock(
            return_value={
                "code": "0",
                "data": [
                    {
                        "last": "50000",
                        "bidPx": "49999",
                        "askPx": "50001",
                        "vol24h": "1000000",
                        "sodUtc8": "1.5",
                    }
                ],
            }
        )
        ticker = await rest_client.get_ticker("BTC-USDT-SWAP")
        assert ticker.last == 50000.0
        assert ticker.bid == 49999.0


class TestGetFundingRate:
    @pytest.mark.asyncio
    async def test_get_funding_rate_success(self, rest_client: OKXRestClient) -> None:
        rest_client._public_api = MagicMock()
        rest_client._public_api.get_funding_rate = MagicMock(
            return_value={
                "code": "0",
                "data": [{"fundingRate": "0.0001", "nextFundingRate": "0.0002"}],
            }
        )
        funding = await rest_client.get_funding_rate("BTC-USDT-SWAP")
        assert funding.current == 0.0001
        assert funding.predicted == 0.0002


class TestGetOpenInterest:
    @pytest.mark.asyncio
    async def test_get_open_interest_success(self, rest_client: OKXRestClient) -> None:
        rest_client._public_api = MagicMock()
        rest_client._public_api.get_open_interest = MagicMock(
            return_value={"code": "0", "data": [{"oi": "50000"}]}
        )
        oi = await rest_client.get_open_interest("BTC-USDT-SWAP")
        assert oi.oi == 50000.0


class TestGetLongShortRatio:
    @pytest.mark.asyncio
    async def test_get_long_short_ratio_success(self, rest_client: OKXRestClient) -> None:
        rest_client._market_api = MagicMock()
        rest_client._market_api.get_taker_volume = MagicMock(
            return_value={
                "code": "0",
                "data": [["1700000000000", "100", "80", "1.25", "BTC-USDT-SWAP"]],
            }
        )
        ratio = await rest_client.get_long_short_ratio("BTC-USDT-SWAP")
        assert ratio == 1.25


class TestGetTakerVolume:
    @pytest.mark.asyncio
    async def test_get_taker_volume_success(self, rest_client: OKXRestClient) -> None:
        rest_client._market_api = MagicMock()
        rest_client._market_api.get_taker_volume = MagicMock(
            return_value={
                "code": "0",
                "data": [["1700000000000", "100", "80", "1.25", "BTC-USDT-SWAP"]],
            }
        )
        ratio = await rest_client.get_taker_volume("BTC-USDT-SWAP")
        assert isinstance(ratio, float)
