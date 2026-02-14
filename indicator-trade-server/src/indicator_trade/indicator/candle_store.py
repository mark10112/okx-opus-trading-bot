"""In-memory candle storage (deque) + DB persistence."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import TYPE_CHECKING

import pandas as pd
import structlog

if TYPE_CHECKING:
    from indicator_trade.db.candle_repository import CandleRepository
    from indicator_trade.models.candle import Candle

logger = structlog.get_logger()


class CandleStore:
    """
    In-memory candle storage using deque (FIFO, max 200 per instrument+timeframe)
    + persist to TimescaleDB for historical queries.

    Structure: candles[instrument][timeframe] = deque([Candle, ...])
    """

    def __init__(self, db_repo: CandleRepository, max_candles: int = 200) -> None:
        self.db_repo = db_repo
        self.max_candles = max_candles
        self.candles: dict[str, dict[str, deque[Candle]]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=max_candles))
        )

    async def add(self, instrument: str, timeframe: str, candle: Candle) -> None:
        """Append to in-memory deque + persist to DB (upsert on conflict)."""
        ...

    def get(self, instrument: str, timeframe: str, limit: int = 100) -> list[Candle]:
        """Get last N candles from in-memory store."""
        ...

    def get_latest(self, instrument: str, timeframe: str) -> Candle | None:
        """Get the most recent candle."""
        ...

    def get_as_dataframe(
        self, instrument: str, timeframe: str, limit: int = 100
    ) -> pd.DataFrame:
        """
        Convert candles to pandas DataFrame for pandas-ta:
        columns: ['open', 'high', 'low', 'close', 'volume']
        index: DatetimeIndex
        """
        ...

    async def backfill(
        self, instrument: str, timeframe: str, candles: list[Candle]
    ) -> None:
        """Bulk insert historical candles to memory + DB."""
        ...
