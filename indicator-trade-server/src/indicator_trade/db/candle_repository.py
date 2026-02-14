"""Candle CRUD (TimescaleDB)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if TYPE_CHECKING:
    from indicator_trade.models.candle import Candle

logger = structlog.get_logger()


class CandleRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def upsert(self, candle: Candle) -> None:
        """Insert or update a single candle (ON CONFLICT DO UPDATE)."""
        async with self.session_factory() as session:
            await session.execute(
                text("""
                    INSERT INTO candles (time, symbol, timeframe, open, high, low, close, volume)
                    VALUES (:time, :symbol, :timeframe, :open, :high, :low, :close, :volume)
                    ON CONFLICT (time, symbol, timeframe)
                    DO UPDATE SET open = EXCLUDED.open, high = EXCLUDED.high,
                                  low = EXCLUDED.low, close = EXCLUDED.close,
                                  volume = EXCLUDED.volume
                """),
                {
                    "time": candle.time,
                    "symbol": candle.symbol,
                    "timeframe": candle.timeframe,
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                },
            )
            await session.commit()

    async def bulk_insert(self, candles: list[Candle]) -> None:
        """Bulk insert candles."""
        async with self.session_factory() as session:
            for candle in candles:
                await session.execute(
                    text("""
                        INSERT INTO candles (time, symbol, timeframe, open, high, low, close, volume)
                        VALUES (:time, :symbol, :timeframe, :open, :high, :low, :close, :volume)
                        ON CONFLICT (time, symbol, timeframe) DO NOTHING
                    """),
                    {
                        "time": candle.time,
                        "symbol": candle.symbol,
                        "timeframe": candle.timeframe,
                        "open": candle.open,
                        "high": candle.high,
                        "low": candle.low,
                        "close": candle.close,
                        "volume": candle.volume,
                    },
                )
            await session.commit()

    async def get_recent(
        self, symbol: str, timeframe: str, limit: int = 200
    ) -> list[dict]:
        """Get recent candles ordered by time DESC."""
        async with self.session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT time, symbol, timeframe, open, high, low, close, volume
                    FROM candles
                    WHERE symbol = :symbol AND timeframe = :timeframe
                    ORDER BY time DESC
                    LIMIT :limit
                """),
                {"symbol": symbol, "timeframe": timeframe, "limit": limit},
            )
            return [dict(row._mapping) for row in result.fetchall()]
