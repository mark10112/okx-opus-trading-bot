"""Assemble MarketSnapshot from all data sources."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from indicator_trade.indicator.candle_store import CandleStore
    from indicator_trade.indicator.indicators import TechnicalIndicators
    from indicator_trade.indicator.regime_detector import RegimeDetector
    from indicator_trade.models.snapshot import (
        FundingRate,
        MarketSnapshot,
        OpenInterest,
        OrderBook,
        Ticker,
    )

logger = structlog.get_logger()


class SnapshotBuilder:
    def __init__(
        self,
        candle_store: CandleStore,
        indicators: TechnicalIndicators,
        regime_detector: RegimeDetector,
    ) -> None:
        self.candle_store = candle_store
        self.indicators = indicators
        self.regime_detector = regime_detector

    def build(
        self,
        instrument: str,
        ticker: Ticker,
        orderbook: OrderBook,
        funding: FundingRate,
        oi: OpenInterest,
        ls_ratio: float,
        taker_volume: float,
    ) -> MarketSnapshot:
        """
        Assemble MarketSnapshot:
        1. Get candles from CandleStore (15m, 1H, 4H)
        2. Compute indicators for each timeframe
        3. Detect market regime from 4H data
        4. Calculate derived metrics
        5. Return complete MarketSnapshot
        """
        ...
