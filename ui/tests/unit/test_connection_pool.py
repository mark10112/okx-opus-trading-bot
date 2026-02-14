"""Tests for connection pool configuration (DB engine + Redis client)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ui.config import Settings


class TestDBEnginePoolConfig:
    """Test create_db_engine with configurable pool parameters."""

    def test_default_pool_params(self):
        """Engine uses sensible defaults for pool_recycle, pool_timeout, pool_use_lifo."""
        from ui.db.engine import create_db_engine

        engine = create_db_engine("postgresql+asyncpg://localhost/test")
        pool = engine.pool
        assert pool.size() == 5
        assert pool._max_overflow == 5
        assert pool._recycle == 1800
        assert pool._timeout == 30
        engine.sync_engine.dispose()

    def test_custom_pool_params(self):
        """Engine respects custom pool params."""
        from ui.db.engine import create_db_engine

        engine = create_db_engine(
            "postgresql+asyncpg://localhost/test",
            pool_size=3,
            max_overflow=3,
            pool_recycle=600,
            pool_timeout=10,
        )
        pool = engine.pool
        assert pool.size() == 3
        assert pool._max_overflow == 3
        assert pool._recycle == 600
        assert pool._timeout == 10
        engine.sync_engine.dispose()


class TestSettingsPoolConfig:
    """Test Settings has DB pool configuration fields."""

    def test_default_db_pool_settings(self):
        settings = Settings()
        assert settings.DB_POOL_SIZE == 5
        assert settings.DB_MAX_OVERFLOW == 5
        assert settings.DB_POOL_RECYCLE == 1800
        assert settings.DB_POOL_TIMEOUT == 30

    def test_custom_db_pool_settings(self):
        settings = Settings(
            DB_POOL_SIZE=3,
            DB_MAX_OVERFLOW=3,
            DB_POOL_RECYCLE=600,
            DB_POOL_TIMEOUT=10,
        )
        assert settings.DB_POOL_SIZE == 3
        assert settings.DB_MAX_OVERFLOW == 3
        assert settings.DB_POOL_RECYCLE == 600
        assert settings.DB_POOL_TIMEOUT == 10


class TestRedisClientTimeouts:
    """Test RedisClient with socket timeouts and retry_on_timeout."""

    def test_default_socket_timeouts(self):
        from ui.redis_client import RedisClient

        client = RedisClient(redis_url="redis://localhost:6379")
        assert client.socket_timeout == 30.0
        assert client.socket_connect_timeout == 10.0
        assert client.retry_on_timeout is True

    def test_custom_socket_timeouts(self):
        from ui.redis_client import RedisClient

        client = RedisClient(
            redis_url="redis://localhost:6379",
            socket_timeout=15.0,
            socket_connect_timeout=8.0,
            retry_on_timeout=False,
        )
        assert client.socket_timeout == 15.0
        assert client.socket_connect_timeout == 8.0
        assert client.retry_on_timeout is False

    @pytest.mark.asyncio
    async def test_connect_uses_timeout_params(self):
        from ui.redis_client import RedisClient

        client = RedisClient(
            redis_url="redis://localhost:6379",
            socket_timeout=15.0,
            socket_connect_timeout=8.0,
        )

        with patch("ui.redis_client.aioredis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            await client.connect()

            mock_from_url.assert_called_once_with(
                "redis://localhost:6379",
                decode_responses=False,
                max_connections=20,
                socket_timeout=15.0,
                socket_connect_timeout=8.0,
                retry_on_timeout=True,
            )
