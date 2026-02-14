"""Entry point: start Telegram bot + alert listener."""

import asyncio
import signal

import structlog

from ui.config import Settings
from ui.redis_client import RedisClient

logger = structlog.get_logger()


async def main() -> None:
    settings = Settings()

    redis = RedisClient(
        redis_url=settings.REDIS_URL,
        consumer_group="ui",
        consumer_name="ui-1",
    )
    await redis.connect()

    # Import here to avoid circular imports during startup
    from ui.db.engine import create_db_engine
    from ui.db.queries import DBQueries
    from ui.telegram.bot import TelegramBot

    engine = create_db_engine(settings.DATABASE_URL)
    db_queries = DBQueries(engine=engine)
    bot = TelegramBot(settings=settings, redis=redis, db_queries=db_queries)

    loop = asyncio.get_running_loop()

    def _signal_handler() -> None:
        logger.info("shutdown_signal_received")
        asyncio.ensure_future(bot.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    try:
        await bot.start()
    except asyncio.CancelledError:
        pass
    finally:
        await redis.disconnect()
        logger.info("shutdown_complete")


if __name__ == "__main__":
    asyncio.run(main())
