"""Unit tests for RegimeDetector — market regime classification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from indicator_trade.indicator.regime_detector import RegimeDetector
from indicator_trade.models.indicator_set import IndicatorSet


def _make_4h_df(rows: int = 60, base_price: float = 100.0) -> pd.DataFrame:
    """Generate a 4H OHLCV DataFrame."""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(timezone.utc), periods=rows, freq="4h")
    close = base_price + np.cumsum(np.random.randn(rows) * 0.5)
    high = close + np.abs(np.random.randn(rows) * 0.3)
    low = close - np.abs(np.random.randn(rows) * 0.3)
    open_ = close + np.random.randn(rows) * 0.2
    volume = np.abs(np.random.randn(rows) * 1000) + 500
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


@pytest.fixture
def detector() -> RegimeDetector:
    return RegimeDetector()


@pytest.fixture
def sample_4h_df() -> pd.DataFrame:
    return _make_4h_df(60)


# --- _classify() boundary tests ---


class TestClassify:
    """Test the _classify method with boundary values for ADX=25, slope=±0.002, ATR ratio=1.5."""

    def test_trending_up_adx_above_slope_positive(self, detector: RegimeDetector) -> None:
        """ADX > 25 AND slope > 0.002 => trending_up."""
        assert detector._classify(adx=30.0, atr_ratio=1.0, ema_slope=0.003) == "trending_up"

    def test_trending_down_adx_above_slope_negative(self, detector: RegimeDetector) -> None:
        """ADX > 25 AND slope < -0.002 => trending_down."""
        assert detector._classify(adx=30.0, atr_ratio=1.0, ema_slope=-0.003) == "trending_down"

    def test_volatile_atr_ratio_above_threshold(self, detector: RegimeDetector) -> None:
        """ATR ratio > 1.5 (and not trending) => volatile."""
        assert detector._classify(adx=20.0, atr_ratio=2.0, ema_slope=0.0) == "volatile"

    def test_ranging_default(self, detector: RegimeDetector) -> None:
        """No conditions met => ranging."""
        assert detector._classify(adx=20.0, atr_ratio=1.0, ema_slope=0.0) == "ranging"

    # --- Boundary: ADX exactly 25 ---

    def test_adx_at_boundary_25_with_positive_slope(self, detector: RegimeDetector) -> None:
        """ADX == 25 is NOT > 25, so should not be trending."""
        result = detector._classify(adx=25.0, atr_ratio=1.0, ema_slope=0.003)
        assert result == "ranging"

    def test_adx_just_above_25(self, detector: RegimeDetector) -> None:
        """ADX = 25.01 with positive slope => trending_up."""
        assert detector._classify(adx=25.01, atr_ratio=1.0, ema_slope=0.003) == "trending_up"

    def test_adx_just_below_25(self, detector: RegimeDetector) -> None:
        """ADX = 24.99 => not trending."""
        result = detector._classify(adx=24.99, atr_ratio=1.0, ema_slope=0.003)
        assert result != "trending_up"

    # --- Boundary: slope exactly ±0.002 ---

    def test_slope_at_positive_boundary(self, detector: RegimeDetector) -> None:
        """slope == 0.002 is NOT > 0.002, so not trending_up."""
        result = detector._classify(adx=30.0, atr_ratio=1.0, ema_slope=0.002)
        assert result != "trending_up"

    def test_slope_just_above_positive_boundary(self, detector: RegimeDetector) -> None:
        """slope = 0.0021 => trending_up."""
        assert detector._classify(adx=30.0, atr_ratio=1.0, ema_slope=0.0021) == "trending_up"

    def test_slope_at_negative_boundary(self, detector: RegimeDetector) -> None:
        """slope == -0.002 is NOT < -0.002, so not trending_down."""
        result = detector._classify(adx=30.0, atr_ratio=1.0, ema_slope=-0.002)
        assert result != "trending_down"

    def test_slope_just_below_negative_boundary(self, detector: RegimeDetector) -> None:
        """slope = -0.0021 => trending_down."""
        assert detector._classify(adx=30.0, atr_ratio=1.0, ema_slope=-0.0021) == "trending_down"

    # --- Boundary: ATR ratio exactly 1.5 ---

    def test_atr_ratio_at_boundary(self, detector: RegimeDetector) -> None:
        """ATR ratio == 1.5 is NOT > 1.5, so not volatile."""
        result = detector._classify(adx=20.0, atr_ratio=1.5, ema_slope=0.0)
        assert result == "ranging"

    def test_atr_ratio_just_above_boundary(self, detector: RegimeDetector) -> None:
        """ATR ratio = 1.51 => volatile."""
        assert detector._classify(adx=20.0, atr_ratio=1.51, ema_slope=0.0) == "volatile"

    # --- Priority: trending takes precedence over volatile ---

    def test_trending_takes_precedence_over_volatile(self, detector: RegimeDetector) -> None:
        """When both trending and volatile conditions met, trending wins."""
        result = detector._classify(adx=30.0, atr_ratio=2.0, ema_slope=0.003)
        assert result == "trending_up"


# --- detect() integration ---


class TestDetect:
    def test_detect_returns_valid_regime(
        self, detector: RegimeDetector, sample_4h_df: pd.DataFrame
    ) -> None:
        indicators = IndicatorSet(adx=30.0, atr=1.0, ema={20: 101.0, 50: 100.0, 200: 99.0})
        result = detector.detect(sample_4h_df, indicators)
        assert result in ("trending_up", "trending_down", "ranging", "volatile")

    def test_detect_with_none_adx_returns_ranging(
        self, detector: RegimeDetector, sample_4h_df: pd.DataFrame
    ) -> None:
        """When ADX is None, should default to ranging."""
        indicators = IndicatorSet(adx=None, atr=1.0, ema={20: 101.0})
        result = detector.detect(sample_4h_df, indicators)
        assert result in ("ranging", "volatile")

    def test_detect_with_none_atr_returns_non_volatile(
        self, detector: RegimeDetector, sample_4h_df: pd.DataFrame
    ) -> None:
        """When ATR is None, can't compute ATR ratio, so not volatile."""
        indicators = IndicatorSet(adx=20.0, atr=None, ema={20: 101.0})
        result = detector.detect(sample_4h_df, indicators)
        assert result == "ranging"

    def test_detect_with_insufficient_ema(
        self, detector: RegimeDetector, sample_4h_df: pd.DataFrame
    ) -> None:
        """When EMA20 not available, slope = 0 => no trending."""
        indicators = IndicatorSet(adx=30.0, atr=1.0, ema={})
        result = detector.detect(sample_4h_df, indicators)
        assert result in ("ranging", "volatile")
