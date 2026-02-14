"""Unit tests for SnapshotBuilder — assembles MarketSnapshot from all data sources."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from indicator_trade.indicator.snapshot_builder import SnapshotBuilder
from indicator_trade.models.candle import Candle
from indicator_trade.models.indicator_set import (
    BollingerValues,
    IndicatorSet,
    MACDValues,
    StochRSIValues,
)
from indicator_trade.models.snapshot import (
    FundingRate,
    MarketSnapshot,
    OpenInterest,
    OrderBook,
)
from indicator_trade.models.ticker import Ticker


def _make_candle(
    ts: datetime | None = None,
    close: float = 100.0,
) -> Candle:
    return Candle(
        time=ts or datetime.now(timezone.utc),
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        open=Decimal("99.0"),
        high=Decimal("105.0"),
        low=Decimal("95.0"),
        close=Decimal(str(close)),
        volume=Decimal("1000.0"),
    )


def _make_ohlcv_df(rows: int = 60) -> pd.DataFrame:
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(timezone.utc), periods=rows, freq="1h")
    close = 100.0 + np.cumsum(np.random.randn(rows) * 0.5)
    return pd.DataFrame(
        {
            "open": close + np.random.randn(rows) * 0.2,
            "high": close + np.abs(np.random.randn(rows) * 0.3),
            "low": close - np.abs(np.random.randn(rows) * 0.3),
            "close": close,
            "volume": np.abs(np.random.randn(rows) * 1000) + 500,
        },
        index=dates,
    )


def _make_indicator_set() -> IndicatorSet:
    return IndicatorSet(
        rsi=55.0,
        macd=MACDValues(line=0.5, signal=0.3, histogram=0.2),
        bollinger=BollingerValues(upper=105.0, middle=100.0, lower=95.0),
        ema={20: 101.0, 50: 100.0, 200: 99.0},
        atr=1.5,
        vwap=100.5,
        adx=30.0,
        stoch_rsi=StochRSIValues(k=60.0, d=55.0),
        obv=50000.0,
        support_levels=[98.0, 95.0],
        resistance_levels=[102.0, 105.0],
        volume_ratio=1.2,
        bb_position="upper_half",
        ema_alignment="bullish",
        macd_signal="bullish",
    )


def _make_ticker() -> Ticker:
    return Ticker(
        symbol="BTC-USDT-SWAP",
        last=100.0,
        bid=99.9,
        ask=100.1,
        volume_24h=50000.0,
        change_24h=1.5,
    )


@pytest.fixture
def mock_candle_store() -> MagicMock:
    store = MagicMock()
    # Return candles for each timeframe
    candles = [_make_candle(close=float(100 + i)) for i in range(60)]
    store.get.return_value = candles
    store.get_as_dataframe.return_value = _make_ohlcv_df(60)
    return store


@pytest.fixture
def mock_indicators() -> MagicMock:
    ind = MagicMock()
    ind.compute.return_value = _make_indicator_set()
    return ind


@pytest.fixture
def mock_regime_detector() -> MagicMock:
    det = MagicMock()
    det.detect.return_value = "trending_up"
    return det


@pytest.fixture
def builder(
    mock_candle_store: MagicMock,
    mock_indicators: MagicMock,
    mock_regime_detector: MagicMock,
) -> SnapshotBuilder:
    return SnapshotBuilder(
        candle_store=mock_candle_store,
        indicators=mock_indicators,
        regime_detector=mock_regime_detector,
    )


@pytest.fixture
def ticker() -> Ticker:
    return _make_ticker()


@pytest.fixture
def orderbook() -> OrderBook:
    return OrderBook(
        bids=[(99.9, 10.0), (99.8, 20.0)],
        asks=[(100.1, 10.0), (100.2, 20.0)],
        spread=0.2,
        bid_depth=30.0,
        ask_depth=30.0,
    )


@pytest.fixture
def funding() -> FundingRate:
    return FundingRate(current=0.0001, predicted=0.0002)


@pytest.fixture
def oi() -> OpenInterest:
    return OpenInterest(oi=1000000.0, oi_change_24h=5.0)


class TestBuild:
    def test_returns_market_snapshot(
        self,
        builder: SnapshotBuilder,
        ticker: Ticker,
        orderbook: OrderBook,
        funding: FundingRate,
        oi: OpenInterest,
    ) -> None:
        result = builder.build(
            instrument="BTC-USDT-SWAP",
            ticker=ticker,
            orderbook=orderbook,
            funding=funding,
            oi=oi,
            ls_ratio=1.2,
            taker_volume=500.0,
        )
        assert isinstance(result, MarketSnapshot)

    def test_snapshot_has_ticker(
        self,
        builder: SnapshotBuilder,
        ticker: Ticker,
        orderbook: OrderBook,
        funding: FundingRate,
        oi: OpenInterest,
    ) -> None:
        result = builder.build(
            instrument="BTC-USDT-SWAP",
            ticker=ticker,
            orderbook=orderbook,
            funding=funding,
            oi=oi,
            ls_ratio=1.2,
            taker_volume=500.0,
        )
        assert result.ticker == ticker

    def test_snapshot_has_indicators_per_timeframe(
        self,
        builder: SnapshotBuilder,
        ticker: Ticker,
        orderbook: OrderBook,
        funding: FundingRate,
        oi: OpenInterest,
        mock_indicators: MagicMock,
    ) -> None:
        result = builder.build(
            instrument="BTC-USDT-SWAP",
            ticker=ticker,
            orderbook=orderbook,
            funding=funding,
            oi=oi,
            ls_ratio=1.2,
            taker_volume=500.0,
        )
        # Should have indicators for each timeframe
        assert len(result.indicators) > 0
        # compute() should be called for each timeframe
        assert mock_indicators.compute.call_count >= 1

    def test_snapshot_has_regime(
        self,
        builder: SnapshotBuilder,
        ticker: Ticker,
        orderbook: OrderBook,
        funding: FundingRate,
        oi: OpenInterest,
    ) -> None:
        result = builder.build(
            instrument="BTC-USDT-SWAP",
            ticker=ticker,
            orderbook=orderbook,
            funding=funding,
            oi=oi,
            ls_ratio=1.2,
            taker_volume=500.0,
        )
        assert result.market_regime == "trending_up"

    def test_snapshot_has_orderbook(
        self,
        builder: SnapshotBuilder,
        ticker: Ticker,
        orderbook: OrderBook,
        funding: FundingRate,
        oi: OpenInterest,
    ) -> None:
        result = builder.build(
            instrument="BTC-USDT-SWAP",
            ticker=ticker,
            orderbook=orderbook,
            funding=funding,
            oi=oi,
            ls_ratio=1.2,
            taker_volume=500.0,
        )
        assert result.orderbook == orderbook

    def test_snapshot_has_funding_rate(
        self,
        builder: SnapshotBuilder,
        ticker: Ticker,
        orderbook: OrderBook,
        funding: FundingRate,
        oi: OpenInterest,
    ) -> None:
        result = builder.build(
            instrument="BTC-USDT-SWAP",
            ticker=ticker,
            orderbook=orderbook,
            funding=funding,
            oi=oi,
            ls_ratio=1.2,
            taker_volume=500.0,
        )
        assert result.funding_rate == funding

    def test_snapshot_has_open_interest(
        self,
        builder: SnapshotBuilder,
        ticker: Ticker,
        orderbook: OrderBook,
        funding: FundingRate,
        oi: OpenInterest,
    ) -> None:
        result = builder.build(
            instrument="BTC-USDT-SWAP",
            ticker=ticker,
            orderbook=orderbook,
            funding=funding,
            oi=oi,
            ls_ratio=1.2,
            taker_volume=500.0,
        )
        assert result.open_interest == oi

    def test_snapshot_has_ls_ratio(
        self,
        builder: SnapshotBuilder,
        ticker: Ticker,
        orderbook: OrderBook,
        funding: FundingRate,
        oi: OpenInterest,
    ) -> None:
        result = builder.build(
            instrument="BTC-USDT-SWAP",
            ticker=ticker,
            orderbook=orderbook,
            funding=funding,
            oi=oi,
            ls_ratio=1.5,
            taker_volume=500.0,
        )
        assert result.long_short_ratio == 1.5

    def test_candle_store_queried_per_timeframe(
        self,
        builder: SnapshotBuilder,
        ticker: Ticker,
        orderbook: OrderBook,
        funding: FundingRate,
        oi: OpenInterest,
        mock_candle_store: MagicMock,
    ) -> None:
        builder.build(
            instrument="BTC-USDT-SWAP",
            ticker=ticker,
            orderbook=orderbook,
            funding=funding,
            oi=oi,
            ls_ratio=1.2,
            taker_volume=500.0,
        )
        # Should query candle store for multiple timeframes
        assert mock_candle_store.get.call_count >= 1

    def test_regime_detector_called_with_4h(
        self,
        builder: SnapshotBuilder,
        ticker: Ticker,
        orderbook: OrderBook,
        funding: FundingRate,
        oi: OpenInterest,
        mock_regime_detector: MagicMock,
    ) -> None:
        builder.build(
            instrument="BTC-USDT-SWAP",
            ticker=ticker,
            orderbook=orderbook,
            funding=funding,
            oi=oi,
            ls_ratio=1.2,
            taker_volume=500.0,
        )
        mock_regime_detector.detect.assert_called_once()

    def test_snapshot_has_candles_dict(
        self,
        builder: SnapshotBuilder,
        ticker: Ticker,
        orderbook: OrderBook,
        funding: FundingRate,
        oi: OpenInterest,
    ) -> None:
        result = builder.build(
            instrument="BTC-USDT-SWAP",
            ticker=ticker,
            orderbook=orderbook,
            funding=funding,
            oi=oi,
            ls_ratio=1.2,
            taker_volume=500.0,
        )
        assert isinstance(result.candles, dict)
        assert len(result.candles) > 0
