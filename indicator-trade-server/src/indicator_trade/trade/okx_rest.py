"""OKX REST API wrapper (python-okx SDK)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from indicator_trade.models.candle import Candle
    from indicator_trade.models.order import OrderRequest, OrderResult
    from indicator_trade.models.position import AccountState, Position
    from indicator_trade.models.snapshot import FundingRate, OpenInterest, OrderBook, Ticker

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
        # SDK clients initialized here in implementation phase
        ...

    async def get_balance(self) -> AccountState: ...

    async def get_positions(self, instId: str | None = None) -> list[Position]: ...

    async def set_leverage(self, instId: str, lever: str, mgnMode: str = "cross") -> dict: ...

    async def place_order(self, request: OrderRequest) -> OrderResult: ...

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
    ) -> dict: ...

    async def cancel_order(self, instId: str, ordId: str) -> dict: ...

    async def close_position(self, instId: str, mgnMode: str, posSide: str) -> dict: ...

    async def get_candles(self, instId: str, bar: str, limit: int = 200) -> list[Candle]: ...

    async def get_ticker(self, instId: str) -> Ticker: ...

    async def get_orderbook(self, instId: str, sz: int = 20) -> OrderBook: ...

    async def get_funding_rate(self, instId: str) -> FundingRate: ...

    async def get_open_interest(self, instId: str) -> OpenInterest: ...

    async def get_long_short_ratio(self, instId: str) -> float: ...

    async def get_taker_volume(self, instId: str) -> float: ...
