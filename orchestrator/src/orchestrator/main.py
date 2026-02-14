"""Entry point: start orchestrator main loop."""

import asyncio
import signal
import sys

import structlog

from orchestrator.config import Settings
from orchestrator.db.engine import create_db_engine
from orchestrator.redis_client import RedisClient
from orchestrator.state_machine import Orchestrator

logger = structlog.get_logger()


async def main() -> None:
    settings = Settings()

    redis = RedisClient(
        redis_url=settings.REDIS_URL,
        consumer_group="orchestrator",
        consumer_name="orch-1",
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

    orchestrator = Orchestrator(settings=settings, redis=redis)

    loop = asyncio.get_running_loop()

    def _signal_handler() -> None:
        logger.info("shutdown_signal_received")
        orchestrator.running = False

    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _signal_handler)
    else:
        signal.signal(signal.SIGINT, lambda *_: _signal_handler())

    try:
        await orchestrator.start()
    except asyncio.CancelledError:
        pass
    finally:
        await orchestrator.stop()
        await redis.disconnect()
        await engine.dispose()
        logger.info("shutdown_complete")


if __name__ == "__main__":
    asyncio.run(main())
