"""Entry point: start both indicator server and trade server."""

import asyncio
import signal
import sys

import structlog

from indicator_trade.config import Settings
from indicator_trade.db.engine import create_db_engine
from indicator_trade.indicator.server import IndicatorServer
from indicator_trade.redis_client import RedisClient
from indicator_trade.trade.server import TradeServer

logger = structlog.get_logger()


async def main() -> None:
    settings = Settings()

    redis = RedisClient(
        redis_url=settings.REDIS_URL,
        consumer_group="indicator_trade",
        consumer_name="indicator-trade-1",
        socket_timeout=30.0,
        socket_connect_timeout=10.0,
        retry_on_timeout=True,
    )
    await redis.connect()

    engine = create_db_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_timeout=settings.DB_POOL_TIMEOUT,
    )

    indicator_server = IndicatorServer(settings=settings, redis=redis)
    trade_server = TradeServer(settings=settings, redis=redis)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("shutdown_signal_received")
        stop_event.set()

    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _signal_handler)
    else:
        signal.signal(signal.SIGINT, lambda *_: _signal_handler())

    try:
        await asyncio.gather(
            indicator_server.start(),
            trade_server.start(),
        )
    except asyncio.CancelledError:
        pass
    finally:
        await indicator_server.stop()
        await trade_server.stop()
        await redis.disconnect()
        await engine.dispose()
        logger.info("shutdown_complete")


if __name__ == "__main__":
    asyncio.run(main())
