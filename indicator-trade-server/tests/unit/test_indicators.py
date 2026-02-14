"""Unit tests for TechnicalIndicators (pandas-ta based computation)."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from indicator_trade.indicator.indicators import TechnicalIndicators
from indicator_trade.models.indicator_set import IndicatorSet


def _make_ohlcv_df(rows: int = 200, base_price: float = 100.0) -> pd.DataFrame:
    """Generate a realistic OHLCV DataFrame for testing."""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(timezone.utc), periods=rows, freq="1h")
    close = base_price + np.cumsum(np.random.randn(rows) * 0.5)
    high = close + np.abs(np.random.randn(rows) * 0.3)
    low = close - np.abs(np.random.randn(rows) * 0.3)
    open_ = close + np.random.randn(rows) * 0.2
    volume = np.abs(np.random.randn(rows) * 1000) + 500

    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dates,
    )


@pytest.fixture
def indicators() -> TechnicalIndicators:
    return TechnicalIndicators()


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return _make_ohlcv_df(200)


@pytest.fixture
def small_df() -> pd.DataFrame:
    return _make_ohlcv_df(5)


# --- compute() returns IndicatorSet ---


class TestCompute:
    def test_returns_indicator_set(
        self, indicators: TechnicalIndicators, sample_df: pd.DataFrame
    ) -> None:
        result = indicators.compute(sample_df)
        assert isinstance(result, IndicatorSet)

    def test_rsi_in_range(self, indicators: TechnicalIndicators, sample_df: pd.DataFrame) -> None:
        result = indicators.compute(sample_df)
        assert result.rsi is not None
        assert 0.0 <= result.rsi <= 100.0

    def test_macd_populated(self, indicators: TechnicalIndicators, sample_df: pd.DataFrame) -> None:
        result = indicators.compute(sample_df)
        assert result.macd is not None
        assert isinstance(result.macd.line, float)
        assert isinstance(result.macd.signal, float)
        assert isinstance(result.macd.histogram, float)

    def test_bollinger_bands_order(
        self, indicators: TechnicalIndicators, sample_df: pd.DataFrame
    ) -> None:
        result = indicators.compute(sample_df)
        assert result.bollinger is not None
        assert result.bollinger.lower <= result.bollinger.middle <= result.bollinger.upper

    def test_ema_values(self, indicators: TechnicalIndicators, sample_df: pd.DataFrame) -> None:
        result = indicators.compute(sample_df)
        assert 20 in result.ema
        assert 50 in result.ema
        assert 200 in result.ema
        for period, val in result.ema.items():
            assert isinstance(val, float)

    def test_atr_positive(self, indicators: TechnicalIndicators, sample_df: pd.DataFrame) -> None:
        result = indicators.compute(sample_df)
        assert result.atr is not None
        assert result.atr > 0.0

    def test_vwap_populated(self, indicators: TechnicalIndicators, sample_df: pd.DataFrame) -> None:
        result = indicators.compute(sample_df)
        assert result.vwap is not None
        assert isinstance(result.vwap, float)

    def test_adx_in_range(self, indicators: TechnicalIndicators, sample_df: pd.DataFrame) -> None:
        result = indicators.compute(sample_df)
        assert result.adx is not None
        assert 0.0 <= result.adx <= 100.0

    def test_stoch_rsi_in_range(
        self, indicators: TechnicalIndicators, sample_df: pd.DataFrame
    ) -> None:
        result = indicators.compute(sample_df)
        assert result.stoch_rsi is not None
        assert 0.0 <= result.stoch_rsi.k <= 100.0
        assert 0.0 <= result.stoch_rsi.d <= 100.0

    def test_obv_populated(self, indicators: TechnicalIndicators, sample_df: pd.DataFrame) -> None:
        result = indicators.compute(sample_df)
        assert result.obv is not None
        assert isinstance(result.obv, float)

    def test_ichimoku_populated(
        self, indicators: TechnicalIndicators, sample_df: pd.DataFrame
    ) -> None:
        result = indicators.compute(sample_df)
        assert result.ichimoku is not None
        assert isinstance(result.ichimoku.tenkan, float)
        assert isinstance(result.ichimoku.kijun, float)
        assert isinstance(result.ichimoku.senkou_a, float)
        assert isinstance(result.ichimoku.senkou_b, float)

    def test_support_resistance_lists(
        self, indicators: TechnicalIndicators, sample_df: pd.DataFrame
    ) -> None:
        result = indicators.compute(sample_df)
        assert isinstance(result.support_levels, list)
        assert isinstance(result.resistance_levels, list)

    def test_volume_ratio_positive(
        self, indicators: TechnicalIndicators, sample_df: pd.DataFrame
    ) -> None:
        result = indicators.compute(sample_df)
        assert result.volume_ratio > 0.0


# --- Derived signals ---


class TestDerivedSignals:
    def test_bb_position_valid(
        self, indicators: TechnicalIndicators, sample_df: pd.DataFrame
    ) -> None:
        result = indicators.compute(sample_df)
        assert result.bb_position in ("above", "below", "upper_half", "lower_half")

    def test_ema_alignment_valid(
        self, indicators: TechnicalIndicators, sample_df: pd.DataFrame
    ) -> None:
        result = indicators.compute(sample_df)
        assert result.ema_alignment in ("bullish", "bearish", "neutral")

    def test_macd_signal_valid(
        self, indicators: TechnicalIndicators, sample_df: pd.DataFrame
    ) -> None:
        result = indicators.compute(sample_df)
        assert result.macd_signal in ("bullish", "bearish", "neutral")


# --- Insufficient data handling ---


class TestInsufficientData:
    def test_small_df_returns_indicator_set(
        self, indicators: TechnicalIndicators, small_df: pd.DataFrame
    ) -> None:
        result = indicators.compute(small_df)
        assert isinstance(result, IndicatorSet)

    def test_small_df_none_fields(
        self, indicators: TechnicalIndicators, small_df: pd.DataFrame
    ) -> None:
        """With only 5 rows, most indicators should be None."""
        result = indicators.compute(small_df)
        # RSI needs 14 periods, so should be None with 5 rows
        assert result.rsi is None

    def test_empty_df_returns_default_indicator_set(self, indicators: TechnicalIndicators) -> None:
        empty_df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        result = indicators.compute(empty_df)
        assert isinstance(result, IndicatorSet)
        assert result.rsi is None
        assert result.macd is None
        assert result.bollinger is None
