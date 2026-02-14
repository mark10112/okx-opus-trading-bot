"""Fixtures for indicator-trade-server tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import numpy as np
import pandas as pd
import pytest

from indicator_trade.models.candle import Candle
from indicator_trade.models.indicator_set import (
    BollingerValues,
    IndicatorSet,
    MACDValues,
    StochRSIValues,
)
from indicator_trade.models.snapshot import FundingRate, OpenInterest, OrderBook
from indicator_trade.models.ticker import Ticker


# --- Candle helpers ---


def _make_candle(
    ts: datetime | None = None,
    symbol: str = "BTC-USDT-SWAP",
    timeframe: str = "1H",
    open_: float = 100.0,
    high: float = 105.0,
    low: float = 95.0,
    close: float = 102.0,
    volume: float = 1000.0,
) -> Candle:
    return Candle(
        time=ts or datetime.now(timezone.utc),
        symbol=symbol,
        timeframe=timeframe,
        open=Decimal(str(open_)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=Decimal(str(volume)),
    )


@pytest.fixture
def sample_candle() -> Candle:
    return _make_candle()


@pytest.fixture
def sample_candles() -> list[Candle]:
    now = datetime.now(timezone.utc)
    return [_make_candle(ts=now - timedelta(hours=i), close=float(100 + i)) for i in range(10)]


# --- DataFrame helpers ---


def _make_ohlcv_df(rows: int = 200, base_price: float = 100.0, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)
    dates = pd.date_range(end=datetime.now(timezone.utc), periods=rows, freq="1h")
    close = base_price + np.cumsum(np.random.randn(rows) * 0.5)
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


@pytest.fixture
def sample_df_200() -> pd.DataFrame:
    return _make_ohlcv_df(200)


@pytest.fixture
def sample_df_60() -> pd.DataFrame:
    return _make_ohlcv_df(60)


@pytest.fixture
def sample_df_5() -> pd.DataFrame:
    return _make_ohlcv_df(5)


# --- Mock repos ---


@pytest.fixture
def mock_candle_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.upsert = AsyncMock()
    repo.bulk_insert = AsyncMock()
    repo.get_recent = AsyncMock(return_value=[])
    return repo


# --- Model fixtures ---


@pytest.fixture
def sample_indicator_set() -> IndicatorSet:
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


@pytest.fixture
def sample_ticker() -> Ticker:
    return Ticker(
        symbol="BTC-USDT-SWAP",
        last=100.0,
        bid=99.9,
        ask=100.1,
        volume_24h=50000.0,
        change_24h=1.5,
    )


@pytest.fixture
def sample_orderbook() -> OrderBook:
    return OrderBook(
        bids=[(99.9, 10.0), (99.8, 20.0)],
        asks=[(100.1, 10.0), (100.2, 20.0)],
        spread=0.2,
        bid_depth=30.0,
        ask_depth=30.0,
    )


@pytest.fixture
def sample_funding() -> FundingRate:
    return FundingRate(current=0.0001, predicted=0.0002)


@pytest.fixture
def sample_oi() -> OpenInterest:
    return OpenInterest(oi=1000000.0, oi_change_24h=5.0)
