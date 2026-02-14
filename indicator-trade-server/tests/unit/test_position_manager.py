"""Unit tests for position manager."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from indicator_trade.models.position import Position
from indicator_trade.trade.position_manager import PositionManager


# --- Fixtures ---


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.publish = AsyncMock(return_value="msg-id-1")
    return redis


@pytest.fixture
def manager(mock_redis: AsyncMock) -> PositionManager:
    return PositionManager(redis=mock_redis)


def _make_position_data(
    instId: str = "BTC-USDT-SWAP",
    posSide: str = "long",
    pos: str = "1",
    avgPx: str = "50000",
    upl: str = "100",
    uplRatio: str = "0.02",
    lever: str = "3",
    liqPx: str = "45000",
    margin: str = "5000",
    mgnRatio: str = "0.1",
    uTime: str = "1700000000000",
) -> dict:
    return {
        "instId": instId,
        "posSide": posSide,
        "pos": pos,
        "avgPx": avgPx,
        "upl": upl,
        "uplRatio": uplRatio,
        "lever": lever,
        "liqPx": liqPx,
        "margin": margin,
        "mgnRatio": mgnRatio,
        "uTime": uTime,
    }


# --- Update ---


class TestUpdate:
    @pytest.mark.asyncio
    async def test_update_adds_new_position(self, manager: PositionManager) -> None:
        data = _make_position_data()
        position = await manager.update(data)

        assert isinstance(position, Position)
        assert position.instId == "BTC-USDT-SWAP"
        assert position.posSide == "long"
        assert position.pos == 1.0
        assert position.avgPx == 50000.0

    @pytest.mark.asyncio
    async def test_update_stores_in_dict(self, manager: PositionManager) -> None:
        await manager.update(_make_position_data())
        assert "BTC-USDT-SWAP:long" in manager.positions

    @pytest.mark.asyncio
    async def test_update_overwrites_existing(self, manager: PositionManager) -> None:
        await manager.update(_make_position_data(pos="1", avgPx="50000"))
        await manager.update(_make_position_data(pos="2", avgPx="51000"))

        pos = manager.positions["BTC-USDT-SWAP:long"]
        assert pos.pos == 2.0
        assert pos.avgPx == 51000.0

    @pytest.mark.asyncio
    async def test_update_publishes_to_redis(
        self, manager: PositionManager, mock_redis: AsyncMock
    ) -> None:
        await manager.update(_make_position_data())
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == "trade:positions"

    @pytest.mark.asyncio
    async def test_update_removes_closed_position(self, manager: PositionManager) -> None:
        await manager.update(_make_position_data(pos="1"))
        assert "BTC-USDT-SWAP:long" in manager.positions

        await manager.update(_make_position_data(pos="0"))
        assert "BTC-USDT-SWAP:long" not in manager.positions

    @pytest.mark.asyncio
    async def test_update_publishes_close_event(
        self, manager: PositionManager, mock_redis: AsyncMock
    ) -> None:
        await manager.update(_make_position_data(pos="1"))
        mock_redis.publish.reset_mock()

        await manager.update(_make_position_data(pos="0"))
        # Should publish position close event
        assert mock_redis.publish.call_count >= 1

    @pytest.mark.asyncio
    async def test_update_multiple_instruments(self, manager: PositionManager) -> None:
        await manager.update(_make_position_data(instId="BTC-USDT-SWAP", posSide="long"))
        await manager.update(_make_position_data(instId="ETH-USDT-SWAP", posSide="short"))

        assert len(manager.positions) == 2
        assert "BTC-USDT-SWAP:long" in manager.positions
        assert "ETH-USDT-SWAP:short" in manager.positions


# --- Get methods ---


class TestGetAll:
    @pytest.mark.asyncio
    async def test_get_all_empty(self, manager: PositionManager) -> None:
        assert manager.get_all() == []

    @pytest.mark.asyncio
    async def test_get_all_returns_positions(self, manager: PositionManager) -> None:
        await manager.update(_make_position_data(instId="BTC-USDT-SWAP", posSide="long"))
        await manager.update(_make_position_data(instId="ETH-USDT-SWAP", posSide="short"))

        positions = manager.get_all()
        assert len(positions) == 2

    @pytest.mark.asyncio
    async def test_get_all_excludes_closed(self, manager: PositionManager) -> None:
        await manager.update(_make_position_data(pos="1"))
        await manager.update(_make_position_data(pos="0"))

        assert manager.get_all() == []


class TestGet:
    @pytest.mark.asyncio
    async def test_get_existing_position(self, manager: PositionManager) -> None:
        await manager.update(_make_position_data())
        pos = manager.get("BTC-USDT-SWAP", "long")
        assert pos is not None
        assert pos.instId == "BTC-USDT-SWAP"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, manager: PositionManager) -> None:
        assert manager.get("BTC-USDT-SWAP", "long") is None

    @pytest.mark.asyncio
    async def test_get_wrong_side_returns_none(self, manager: PositionManager) -> None:
        await manager.update(_make_position_data(posSide="long"))
        assert manager.get("BTC-USDT-SWAP", "short") is None


# --- is_position_closed ---


class TestIsPositionClosed:
    def test_pos_zero_is_closed(self, manager: PositionManager) -> None:
        assert manager.is_position_closed({"pos": "0"}) is True

    def test_pos_nonzero_is_not_closed(self, manager: PositionManager) -> None:
        assert manager.is_position_closed({"pos": "1"}) is False

    def test_pos_negative_is_not_closed(self, manager: PositionManager) -> None:
        assert manager.is_position_closed({"pos": "-1"}) is False

    def test_pos_missing_is_not_closed(self, manager: PositionManager) -> None:
        assert manager.is_position_closed({}) is False

    def test_pos_empty_string_is_closed(self, manager: PositionManager) -> None:
        assert manager.is_position_closed({"pos": ""}) is True
