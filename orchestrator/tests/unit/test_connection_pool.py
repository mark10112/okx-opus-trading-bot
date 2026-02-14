"""Tests for connection pool configuration (DB engine + Redis client)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.config import Settings


class TestDBEnginePoolConfig:
    """Test create_db_engine with configurable pool parameters."""

    def test_default_pool_params(self):
        """Engine uses sensible defaults for pool_recycle, pool_timeout, pool_use_lifo."""
        from orchestrator.db.engine import create_db_engine

        engine = create_db_engine("postgresql+asyncpg://localhost/test")
        pool = engine.pool
        assert pool.size() == 10
        assert pool._max_overflow == 20
        assert pool._recycle == 1800  # 30 min
        assert pool._timeout == 30
        engine.sync_engine.dispose()

    def test_custom_pool_params(self):
        """Engine respects custom pool params."""
        from orchestrator.db.engine import create_db_engine

        engine = create_db_engine(
            "postgresql+asyncpg://localhost/test",
            pool_size=5,
            max_overflow=10,
            pool_recycle=900,
            pool_timeout=15,
        )
        pool = engine.pool
        assert pool.size() == 5
        assert pool._max_overflow == 10
        assert pool._recycle == 900
        assert pool._timeout == 15
        engine.sync_engine.dispose()

    def test_pool_pre_ping_enabled(self):
        """pool_pre_ping is always True to detect stale connections."""
        from orchestrator.db.engine import create_db_engine

        engine = create_db_engine("postgresql+asyncpg://localhost/test")
        assert engine.pool._pre_ping is True
        engine.sync_engine.dispose()


class TestSettingsPoolConfig:
    """Test Settings has DB pool configuration fields."""

    def test_default_db_pool_settings(self):
        settings = Settings(
            ANTHROPIC_API_KEY="test",
            PERPLEXITY_API_KEY="test",
        )
        assert settings.DB_POOL_SIZE == 10
        assert settings.DB_MAX_OVERFLOW == 20
        assert settings.DB_POOL_RECYCLE == 1800
        assert settings.DB_POOL_TIMEOUT == 30

    def test_custom_db_pool_settings(self):
        settings = Settings(
            ANTHROPIC_API_KEY="test",
            PERPLEXITY_API_KEY="test",
            DB_POOL_SIZE=5,
            DB_MAX_OVERFLOW=10,
            DB_POOL_RECYCLE=900,
            DB_POOL_TIMEOUT=15,
        )
        assert settings.DB_POOL_SIZE == 5
        assert settings.DB_MAX_OVERFLOW == 10
        assert settings.DB_POOL_RECYCLE == 900
        assert settings.DB_POOL_TIMEOUT == 15


class TestRedisClientTimeouts:
    """Test RedisClient with socket timeouts and retry_on_timeout."""

    @pytest.mark.asyncio
    async def test_connect_passes_socket_timeouts(self):
        """RedisClient.connect() passes socket_timeout and socket_connect_timeout."""
        from orchestrator.redis_client import RedisClient

        client = RedisClient(
            redis_url="redis://localhost:6379",
            socket_timeout=10.0,
            socket_connect_timeout=5.0,
            retry_on_timeout=True,
        )
        assert client.socket_timeout == 10.0
        assert client.socket_connect_timeout == 5.0
        assert client.retry_on_timeout is True

    @pytest.mark.asyncio
    async def test_default_socket_timeouts(self):
        """RedisClient uses sensible defaults for socket timeouts."""
        from orchestrator.redis_client import RedisClient

        client = RedisClient(redis_url="redis://localhost:6379")
        assert client.socket_timeout == 30.0
        assert client.socket_connect_timeout == 10.0
        assert client.retry_on_timeout is True

    @pytest.mark.asyncio
    async def test_connect_uses_timeout_params(self):
        """Verify from_url is called with timeout params."""
        from orchestrator.redis_client import RedisClient

        client = RedisClient(
            redis_url="redis://localhost:6379",
            socket_timeout=15.0,
            socket_connect_timeout=8.0,
        )

        with patch("orchestrator.redis_client.aioredis.from_url") as mock_from_url:
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
