"""OKX REST API wrapper (python-okx SDK)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import structlog

from indicator_trade.models.candle import Candle
from indicator_trade.models.order import OrderRequest, OrderResult
from indicator_trade.models.position import AccountState, Position
from indicator_trade.models.snapshot import FundingRate, OpenInterest, OrderBook
from indicator_trade.models.ticker import Ticker

logger = structlog.get_logger()


class OKXRestClient:
    """Wrapper around python-okx SDK. All methods use flag='1' (Demo Trading)."""

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        passphrase: str,
        flag: str = "1",
    ) -> None:
        self.flag = flag
        from okx.Account import AccountAPI
        from okx.MarketData import MarketAPI
        from okx.PublicData import PublicAPI
        from okx.Trade import TradeAPI

        self._trade_api = TradeAPI(api_key, secret_key, passphrase, False, flag)
        self._account_api = AccountAPI(api_key, secret_key, passphrase, False, flag)
        self._market_api = MarketAPI(flag=flag)
        self._public_api = PublicAPI(flag=flag)

    # --- Trade methods ---

    async def place_order(self, request: OrderRequest) -> OrderResult:
        """Place a market or limit order via OKX Trade API."""
        try:
            kwargs = {
                "instId": request.symbol,
                "tdMode": "cross",
                "side": request.side,
                "posSide": request.pos_side,
                "ordType": request.order_type,
                "sz": request.size,
            }
            if request.order_type == "limit" and request.limit_price:
                kwargs["px"] = request.limit_price

            result = await asyncio.to_thread(self._trade_api.place_order, **kwargs)

            if result and result.get("code") == "0":
                data = result["data"][0]
                if data.get("sCode") == "0":
                    return OrderResult(success=True, ord_id=data["ordId"])
                return OrderResult(
                    success=False,
                    error_code=data.get("sCode"),
                    error_message=data.get("sMsg"),
                )
            data = result.get("data", [{}])[0] if result.get("data") else {}
            return OrderResult(
                success=False,
                error_code=data.get("sCode", result.get("code")),
                error_message=data.get("sMsg", result.get("msg", "")),
            )
        except Exception as e:
            logger.exception("place_order_error", symbol=request.symbol)
            return OrderResult(success=False, error_message=str(e))

    async def place_algo_order(
        self,
        instId: str,
        tdMode: str,
        side: str,
        posSide: str,
        sz: str,
        slTriggerPx: str,
        slOrdPx: str = "-1",
        tpTriggerPx: str | None = None,
        tpOrdPx: str = "-1",
    ) -> dict:
        """Place TP/SL algo order."""
        kwargs = {
            "instId": instId,
            "tdMode": tdMode,
            "side": side,
            "posSide": posSide,
            "sz": sz,
            "ordType": "oco",
            "slTriggerPx": slTriggerPx,
            "slOrdPx": slOrdPx,
        }
        if tpTriggerPx:
            kwargs["tpTriggerPx"] = tpTriggerPx
            kwargs["tpOrdPx"] = tpOrdPx

        return await asyncio.to_thread(self._trade_api.place_algo_order, **kwargs)

    async def cancel_order(self, instId: str, ordId: str) -> dict:
        """Cancel an existing order."""
        return await asyncio.to_thread(self._trade_api.cancel_order, instId=instId, ordId=ordId)

    async def close_position(self, instId: str, mgnMode: str, posSide: str) -> dict:
        """Close a position."""
        return await asyncio.to_thread(
            self._trade_api.close_positions,
            instId=instId,
            mgnMode=mgnMode,
            posSide=posSide,
        )

    # --- Account methods ---

    async def get_balance(self) -> AccountState:
        """Get account balance and equity."""
        result = await asyncio.to_thread(self._account_api.get_account_balance)
        if result and result.get("code") == "0" and result.get("data"):
            data = result["data"][0]
            equity = float(data.get("totalEq", 0))
            available = 0.0
            for detail in data.get("details", []):
                if detail.get("ccy") == "USDT":
                    available = float(detail.get("availBal", 0))
                    break
            return AccountState(equity=equity, available_balance=available)
        return AccountState()

    async def get_positions(self, instId: str | None = None) -> list[Position]:
        """Get current positions."""
        kwargs = {}
        if instId:
            kwargs["instId"] = instId
        result = await asyncio.to_thread(self._account_api.get_positions, **kwargs)
        positions = []
        if result and result.get("code") == "0":
            for d in result.get("data", []):
                utime = None
                if d.get("uTime"):
                    utime = datetime.fromtimestamp(int(d["uTime"]) / 1000, tz=timezone.utc)
                positions.append(
                    Position(
                        instId=d.get("instId", ""),
                        posSide=d.get("posSide", ""),
                        pos=float(d.get("pos", 0)),
                        avgPx=float(d.get("avgPx", 0)),
                        upl=float(d.get("upl", 0)),
                        uplRatio=float(d.get("uplRatio", 0)),
                        lever=float(d.get("lever", 1)),
                        liqPx=float(d.get("liqPx", 0)),
                        margin=float(d.get("margin", 0)),
                        mgnRatio=float(d.get("mgnRatio", 0)),
                        uTime=utime,
                    )
                )
        return positions

    async def set_leverage(self, instId: str, lever: str, mgnMode: str = "cross") -> dict:
        """Set leverage for an instrument."""
        return await asyncio.to_thread(
            self._account_api.set_leverage,
            instId=instId,
            lever=lever,
            mgnMode=mgnMode,
        )

    # --- Market methods ---

    async def get_candles(self, instId: str, bar: str, limit: int = 200) -> list[Candle]:
        """Fetch historical candles."""
        result = await asyncio.to_thread(
            self._market_api.get_candlesticks,
            instId=instId,
            bar=bar,
            limit=str(limit),
        )
        candles = []
        if result and result.get("code") == "0":
            for row in reversed(result.get("data", [])):
                candles.append(
                    Candle(
                        time=datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc),
                        symbol=instId,
                        timeframe=bar,
                        open=Decimal(row[1]),
                        high=Decimal(row[2]),
                        low=Decimal(row[3]),
                        close=Decimal(row[4]),
                        volume=Decimal(row[5]),
                    )
                )
        return candles

    async def get_ticker(self, instId: str) -> Ticker:
        """Fetch latest ticker."""
        result = await asyncio.to_thread(self._market_api.get_ticker, instId=instId)
        if result and result.get("code") == "0" and result.get("data"):
            d = result["data"][0]
            return Ticker(
                symbol=instId,
                last=float(d.get("last", 0)),
                bid=float(d.get("bidPx", 0)),
                ask=float(d.get("askPx", 0)),
                volume_24h=float(d.get("vol24h", 0)),
                change_24h=float(d.get("sodUtc8", 0)),
            )
        return Ticker(symbol=instId, last=0, bid=0, ask=0, volume_24h=0, change_24h=0)

    async def get_orderbook(self, instId: str, sz: int = 20) -> OrderBook:
        """Fetch order book."""
        result = await asyncio.to_thread(self._market_api.get_orderbook, instId=instId, sz=str(sz))
        if result and result.get("code") == "0" and result.get("data"):
            d = result["data"][0]
            bids = [(float(b[0]), float(b[1])) for b in d.get("bids", [])]
            asks = [(float(a[0]), float(a[1])) for a in d.get("asks", [])]
            spread = (asks[0][0] - bids[0][0]) if bids and asks else 0.0
            bid_depth = sum(b[1] for b in bids)
            ask_depth = sum(a[1] for a in asks)
            return OrderBook(
                bids=bids,
                asks=asks,
                spread=spread,
                bid_depth=bid_depth,
                ask_depth=ask_depth,
            )
        return OrderBook()

    async def get_funding_rate(self, instId: str) -> FundingRate:
        """Fetch current funding rate."""
        result = await asyncio.to_thread(self._public_api.get_funding_rate, instId=instId)
        if result and result.get("code") == "0" and result.get("data"):
            d = result["data"][0]
            return FundingRate(
                current=float(d.get("fundingRate", 0)),
                predicted=float(d.get("nextFundingRate", 0)),
            )
        return FundingRate()

    async def get_open_interest(self, instId: str) -> OpenInterest:
        """Fetch open interest."""
        result = await asyncio.to_thread(
            self._public_api.get_open_interest, instType="SWAP", instId=instId
        )
        if result and result.get("code") == "0" and result.get("data"):
            d = result["data"][0]
            return OpenInterest(oi=float(d.get("oi", 0)))
        return OpenInterest()

    async def get_long_short_ratio(self, instId: str) -> float:
        """Fetch long/short ratio from taker volume data."""
        result = await asyncio.to_thread(
            self._market_api.get_taker_volume, instId=instId, period="5m"
        )
        if result and result.get("code") == "0" and result.get("data"):
            d = result["data"][0]
            return float(d[3]) if len(d) > 3 else 1.0
        return 1.0

    async def get_taker_volume(self, instId: str) -> float:
        """Fetch taker buy/sell ratio."""
        result = await asyncio.to_thread(
            self._market_api.get_taker_volume, instId=instId, period="5m"
        )
        if result and result.get("code") == "0" and result.get("data"):
            d = result["data"][0]
            return float(d[3]) if len(d) > 3 else 1.0
        return 1.0
