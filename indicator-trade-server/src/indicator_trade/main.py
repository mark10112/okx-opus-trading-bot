"""Entry point: start both indicator server and trade server."""

import asyncio
import signal

import structlog

from indicator_trade.config import Settings
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
    )
    await redis.connect()

    indicator_server = IndicatorServer(settings=settings, redis=redis)
    trade_server = TradeServer(settings=settings, redis=redis)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("shutdown_signal_received")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

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
        logger.info("shutdown_complete")


if __name__ == "__main__":
    asyncio.run(main())
