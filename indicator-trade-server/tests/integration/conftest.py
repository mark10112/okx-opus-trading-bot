"""Shared fixtures for indicator-trade-server integration tests.

OKX live tests require real API keys in .env file.
Redis/DB tests require docker-compose.test.yml running.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

# Load .env from project root for OKX API keys
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))

TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6380")


def _has_okx_keys() -> bool:
    """Check if OKX API keys are available."""
    return bool(
        os.environ.get("OKX_API_KEY")
        and os.environ.get("OKX_SECRET_KEY")
        and os.environ.get("OKX_PASSPHRASE")
    )


@pytest.fixture
def okx_settings():
    """Create Settings with real OKX keys from env."""
    from indicator_trade.config import Settings

    return Settings(
        OKX_API_KEY=os.environ.get("OKX_API_KEY", ""),
        OKX_SECRET_KEY=os.environ.get("OKX_SECRET_KEY", ""),
        OKX_PASSPHRASE=os.environ.get("OKX_PASSPHRASE", ""),
        OKX_FLAG="1",  # Demo trading
        REDIS_URL=TEST_REDIS_URL,
    )
