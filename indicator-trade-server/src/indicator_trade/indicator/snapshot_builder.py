"""Assemble MarketSnapshot from all data sources."""

from __future__ import annotations

from datetime import datetime, timezone
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
)
from indicator_trade.models.ticker import Ticker

logger = structlog.get_logger()

TIMEFRAMES = ["5m", "1H", "4H"]


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
        1. Get candles from CandleStore (5m, 1H, 4H)
        2. Compute indicators for each timeframe
        3. Detect market regime from 4H data
        4. Calculate derived metrics
        5. Return complete MarketSnapshot
        """
        candles_dict = {}
        indicators_dict = {}

        for tf in TIMEFRAMES:
            candles = self.candle_store.get(instrument, tf)
            candles_dict[tf] = candles

            df = self.candle_store.get_as_dataframe(instrument, tf)
            if not df.empty:
                indicators_dict[tf] = self.indicators.compute(df)

        # Detect regime from 4H data
        df_4h = self.candle_store.get_as_dataframe(instrument, "4H")
        regime = "ranging"
        if not df_4h.empty and "4H" in indicators_dict:
            regime = self.regime_detector.detect(df_4h, indicators_dict["4H"])

        # Calculate price_change_1h from 1H candles
        price_change_1h = 0.0
        candles_1h = candles_dict.get("1H", [])
        if len(candles_1h) >= 2:
            prev_close = float(candles_1h[-2].close)
            curr_close = float(candles_1h[-1].close)
            if prev_close > 0:
                price_change_1h = ((curr_close - prev_close) / prev_close) * 100.0

        # Calculate oi_change_4h from OI data
        oi_change_4h = oi.oi_change_24h / 6.0 if oi.oi_change_24h else 0.0

        return MarketSnapshot(
            ticker=ticker,
            candles=candles_dict,
            indicators=indicators_dict,
            orderbook=orderbook,
            funding_rate=funding,
            open_interest=oi,
            long_short_ratio=ls_ratio,
            taker_buy_sell_ratio=taker_volume,
            market_regime=regime,
            price_change_1h=price_change_1h,
            oi_change_4h=oi_change_4h,
            timestamp=datetime.now(timezone.utc),
        )
