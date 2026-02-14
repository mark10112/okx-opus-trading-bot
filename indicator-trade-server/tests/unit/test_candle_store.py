"""Unit tests for CandleStore (in-memory deque + DB persistence)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pandas as pd
import pytest

from indicator_trade.indicator.candle_store import CandleStore
from indicator_trade.models.candle import Candle


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
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.upsert = AsyncMock()
    repo.bulk_insert = AsyncMock()
    return repo


@pytest.fixture
def store(mock_repo: AsyncMock) -> CandleStore:
    return CandleStore(db_repo=mock_repo, max_candles=5)


# --- add() ---


class TestAdd:
    async def test_add_appends_to_deque(self, store: CandleStore, mock_repo: AsyncMock) -> None:
        candle = _make_candle()
        await store.add("BTC-USDT-SWAP", "1H", candle)

        assert len(store.candles["BTC-USDT-SWAP"]["1H"]) == 1
        assert store.candles["BTC-USDT-SWAP"]["1H"][0] is candle

    async def test_add_persists_to_db(self, store: CandleStore, mock_repo: AsyncMock) -> None:
        candle = _make_candle()
        await store.add("BTC-USDT-SWAP", "1H", candle)

        mock_repo.upsert.assert_awaited_once_with(candle)

    async def test_add_respects_max_candles(self, store: CandleStore, mock_repo: AsyncMock) -> None:
        for i in range(7):
            candle = _make_candle(close=float(100 + i))
            await store.add("BTC-USDT-SWAP", "1H", candle)

        # max_candles=5, so only last 5 remain
        assert len(store.candles["BTC-USDT-SWAP"]["1H"]) == 5

    async def test_add_different_instruments(
        self, store: CandleStore, mock_repo: AsyncMock
    ) -> None:
        c1 = _make_candle(symbol="BTC-USDT-SWAP")
        c2 = _make_candle(symbol="ETH-USDT-SWAP")
        await store.add("BTC-USDT-SWAP", "1H", c1)
        await store.add("ETH-USDT-SWAP", "1H", c2)

        assert len(store.candles["BTC-USDT-SWAP"]["1H"]) == 1
        assert len(store.candles["ETH-USDT-SWAP"]["1H"]) == 1

    async def test_add_different_timeframes(self, store: CandleStore, mock_repo: AsyncMock) -> None:
        c1 = _make_candle(timeframe="1H")
        c2 = _make_candle(timeframe="4H")
        await store.add("BTC-USDT-SWAP", "1H", c1)
        await store.add("BTC-USDT-SWAP", "4H", c2)

        assert len(store.candles["BTC-USDT-SWAP"]["1H"]) == 1
        assert len(store.candles["BTC-USDT-SWAP"]["4H"]) == 1


# --- get() ---


class TestGet:
    async def test_get_returns_last_n(self, store: CandleStore, mock_repo: AsyncMock) -> None:
        for i in range(5):
            await store.add("BTC-USDT-SWAP", "1H", _make_candle(close=float(100 + i)))

        result = store.get("BTC-USDT-SWAP", "1H", limit=3)
        assert len(result) == 3

    async def test_get_returns_all_when_fewer(
        self, store: CandleStore, mock_repo: AsyncMock
    ) -> None:
        await store.add("BTC-USDT-SWAP", "1H", _make_candle())

        result = store.get("BTC-USDT-SWAP", "1H", limit=10)
        assert len(result) == 1

    def test_get_empty_returns_empty_list(self, store: CandleStore) -> None:
        result = store.get("BTC-USDT-SWAP", "1H")
        assert result == []

    async def test_get_preserves_order(self, store: CandleStore, mock_repo: AsyncMock) -> None:
        for i in range(3):
            await store.add("BTC-USDT-SWAP", "1H", _make_candle(close=float(100 + i)))

        result = store.get("BTC-USDT-SWAP", "1H", limit=3)
        closes = [float(c.close) for c in result]
        assert closes == [100.0, 101.0, 102.0]


# --- get_latest() ---


class TestGetLatest:
    async def test_get_latest_returns_most_recent(
        self, store: CandleStore, mock_repo: AsyncMock
    ) -> None:
        for i in range(3):
            await store.add("BTC-USDT-SWAP", "1H", _make_candle(close=float(100 + i)))

        latest = store.get_latest("BTC-USDT-SWAP", "1H")
        assert latest is not None
        assert float(latest.close) == 102.0

    def test_get_latest_empty_returns_none(self, store: CandleStore) -> None:
        assert store.get_latest("BTC-USDT-SWAP", "1H") is None


# --- get_as_dataframe() ---


class TestGetAsDataframe:
    async def test_returns_dataframe_with_correct_columns(
        self, store: CandleStore, mock_repo: AsyncMock
    ) -> None:
        for i in range(3):
            await store.add("BTC-USDT-SWAP", "1H", _make_candle(close=float(100 + i)))

        df = store.get_as_dataframe("BTC-USDT-SWAP", "1H")
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]

    async def test_dataframe_has_datetime_index(
        self, store: CandleStore, mock_repo: AsyncMock
    ) -> None:
        await store.add("BTC-USDT-SWAP", "1H", _make_candle())

        df = store.get_as_dataframe("BTC-USDT-SWAP", "1H")
        assert isinstance(df.index, pd.DatetimeIndex)

    async def test_dataframe_values_are_float(
        self, store: CandleStore, mock_repo: AsyncMock
    ) -> None:
        await store.add("BTC-USDT-SWAP", "1H", _make_candle())

        df = store.get_as_dataframe("BTC-USDT-SWAP", "1H")
        for col in df.columns:
            assert df[col].dtype == float

    def test_empty_returns_empty_dataframe(self, store: CandleStore) -> None:
        df = store.get_as_dataframe("BTC-USDT-SWAP", "1H")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]

    async def test_dataframe_respects_limit(self, store: CandleStore, mock_repo: AsyncMock) -> None:
        for i in range(5):
            await store.add("BTC-USDT-SWAP", "1H", _make_candle(close=float(100 + i)))

        df = store.get_as_dataframe("BTC-USDT-SWAP", "1H", limit=3)
        assert len(df) == 3


# --- backfill() ---


class TestBackfill:
    async def test_backfill_adds_to_memory(self, store: CandleStore, mock_repo: AsyncMock) -> None:
        candles = [_make_candle(close=float(100 + i)) for i in range(3)]
        await store.backfill("BTC-USDT-SWAP", "1H", candles)

        assert len(store.candles["BTC-USDT-SWAP"]["1H"]) == 3

    async def test_backfill_persists_to_db(self, store: CandleStore, mock_repo: AsyncMock) -> None:
        candles = [_make_candle(close=float(100 + i)) for i in range(3)]
        await store.backfill("BTC-USDT-SWAP", "1H", candles)

        mock_repo.bulk_insert.assert_awaited_once_with(candles)

    async def test_backfill_respects_max_candles(
        self, store: CandleStore, mock_repo: AsyncMock
    ) -> None:
        candles = [_make_candle(close=float(100 + i)) for i in range(10)]
        await store.backfill("BTC-USDT-SWAP", "1H", candles)

        # max_candles=5
        assert len(store.candles["BTC-USDT-SWAP"]["1H"]) == 5

    async def test_backfill_empty_list(self, store: CandleStore, mock_repo: AsyncMock) -> None:
        await store.backfill("BTC-USDT-SWAP", "1H", [])

        assert len(store.candles["BTC-USDT-SWAP"]["1H"]) == 0
        mock_repo.bulk_insert.assert_awaited_once_with([])
