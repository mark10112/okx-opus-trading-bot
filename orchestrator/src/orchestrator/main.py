"""Entry point: start orchestrator main loop."""

import asyncio
import signal

import structlog

from orchestrator.config import Settings
from orchestrator.redis_client import RedisClient
from orchestrator.state_machine import Orchestrator

logger = structlog.get_logger()


async def main() -> None:
    settings = Settings()

    redis = RedisClient(
        redis_url=settings.REDIS_URL,
        consumer_group="orchestrator",
        consumer_name="orch-1",
    )
    await redis.connect()

    orchestrator = Orchestrator(settings=settings, redis=redis)

    loop = asyncio.get_running_loop()

    def _signal_handler() -> None:
        logger.info("shutdown_signal_received")
        orchestrator.running = False

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    try:
        await orchestrator.start()
    except asyncio.CancelledError:
        pass
    finally:
        await orchestrator.stop()
        await redis.disconnect()
        logger.info("shutdown_complete")


if __name__ == "__main__":
    asyncio.run(main())
