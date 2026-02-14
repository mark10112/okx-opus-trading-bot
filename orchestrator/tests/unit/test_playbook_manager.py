"""Unit tests for PlaybookManager — CRUD via PlaybookRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator.models.playbook import (
    Playbook,
    RegimeRule,
    StrategyDef,
)
from orchestrator.playbook_manager import PlaybookManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def manager(mock_repo):
    return PlaybookManager(mock_repo)


# ---------------------------------------------------------------------------
# get_latest()
# ---------------------------------------------------------------------------


class TestGetLatest:
    async def test_returns_default_when_none_exists(self, manager, mock_repo):
        """get_latest() should return default playbook when DB is empty."""
        mock_repo.get_latest.return_value = None

        playbook = await manager.get_latest()
        assert isinstance(playbook, Playbook)
        assert playbook.version == 1
        assert "trending_up" in playbook.market_regime_rules
        assert "trending_down" in playbook.market_regime_rules
        assert "volatile" in playbook.market_regime_rules
        assert "ranging" in playbook.market_regime_rules
        assert len(playbook.strategy_definitions) >= 4

    async def test_returns_db_playbook_when_exists(self, manager, mock_repo):
        """get_latest() should return playbook from DB when version exists."""
        stored = {
            "version": 3,
            "playbook_json": {
                "version": 3,
                "market_regime_rules": {"trending_up": {"preferred_strategies": ["momentum"]}},
                "strategy_definitions": {},
                "lessons_learned": [],
                "confidence_calibration": {},
                "time_filters": {"avoid_hours_utc": [], "preferred_hours_utc": []},
            },
            "change_summary": "Updated regime rules",
            "triggered_by": "reflection",
            "performance_at_update": {"win_rate": 0.6},
            "created_at": datetime.now(timezone.utc),
        }
        mock_repo.get_latest.return_value = stored

        playbook = await manager.get_latest()
        assert isinstance(playbook, Playbook)
        assert playbook.version == 3

    async def test_saves_default_on_first_load(self, manager, mock_repo):
        """get_latest() should save default playbook to DB when none exists."""
        mock_repo.get_latest.return_value = None
        mock_repo.save_version.return_value = 1

        await manager.get_latest()
        mock_repo.save_version.assert_awaited_once()


# ---------------------------------------------------------------------------
# save_version()
# ---------------------------------------------------------------------------


class TestSaveVersion:
    async def test_increments_version(self, manager, mock_repo):
        """save_version() should save with incremented version."""
        mock_repo.get_latest.return_value = {
            "version": 2,
            "playbook_json": {"version": 2},
            "change_summary": "v2",
            "triggered_by": "reflection",
            "performance_at_update": None,
            "created_at": datetime.now(timezone.utc),
        }
        mock_repo.save_version.return_value = 3

        playbook = Playbook(version=3)
        version = await manager.save_version(
            playbook=playbook,
            change_summary="Added new lesson",
            triggered_by="reflection",
            performance={"win_rate": 0.65},
        )
        assert version == 3
        mock_repo.save_version.assert_awaited_once()
        call_args = mock_repo.save_version.call_args[0][0]
        assert call_args["version"] == 3
        assert call_args["triggered_by"] == "reflection"

    async def test_stores_json(self, manager, mock_repo):
        """save_version() should store playbook as JSON."""
        mock_repo.save_version.return_value = 1

        playbook = Playbook(version=1)
        await manager.save_version(
            playbook=playbook,
            change_summary="Initial",
            triggered_by="init",
            performance={},
        )
        call_args = mock_repo.save_version.call_args[0][0]
        assert "playbook_json" in call_args
        assert isinstance(call_args["playbook_json"], dict)


# ---------------------------------------------------------------------------
# get_version()
# ---------------------------------------------------------------------------


class TestGetVersion:
    async def test_loads_specific_version(self, manager, mock_repo):
        """get_version() should load a specific version from history."""
        mock_repo.get_history.return_value = [
            {
                "version": 2,
                "playbook_json": {
                    "version": 2,
                    "market_regime_rules": {},
                    "strategy_definitions": {},
                    "lessons_learned": [],
                    "confidence_calibration": {},
                    "time_filters": {"avoid_hours_utc": [], "preferred_hours_utc": []},
                },
                "change_summary": "v2",
                "triggered_by": "reflection",
                "performance_at_update": None,
                "created_at": datetime.now(timezone.utc),
            },
            {
                "version": 1,
                "playbook_json": {
                    "version": 1,
                    "market_regime_rules": {},
                    "strategy_definitions": {},
                    "lessons_learned": [],
                    "confidence_calibration": {},
                    "time_filters": {"avoid_hours_utc": [], "preferred_hours_utc": []},
                },
                "change_summary": "v1",
                "triggered_by": "init",
                "performance_at_update": None,
                "created_at": datetime.now(timezone.utc),
            },
        ]

        playbook = await manager.get_version(1)
        assert isinstance(playbook, Playbook)
        assert playbook.version == 1

    async def test_raises_on_not_found(self, manager, mock_repo):
        """get_version() should raise ValueError if version not found."""
        mock_repo.get_history.return_value = []

        with pytest.raises(ValueError, match="Playbook version 99 not found"):
            await manager.get_version(99)


# ---------------------------------------------------------------------------
# get_history()
# ---------------------------------------------------------------------------


class TestGetHistory:
    async def test_returns_ordered_list(self, manager, mock_repo):
        """get_history() should return list of version summaries."""
        mock_repo.get_history.return_value = [
            {
                "version": 2,
                "playbook_json": {"version": 2},
                "change_summary": "v2 changes",
                "triggered_by": "reflection",
                "performance_at_update": None,
                "created_at": datetime.now(timezone.utc),
            },
            {
                "version": 1,
                "playbook_json": {"version": 1},
                "change_summary": "Initial",
                "triggered_by": "init",
                "performance_at_update": None,
                "created_at": datetime.now(timezone.utc),
            },
        ]

        history = await manager.get_history()
        assert len(history) == 2
        assert history[0]["version"] == 2
        assert history[1]["version"] == 1

    async def test_empty_history(self, manager, mock_repo):
        """get_history() should return empty list when no versions."""
        mock_repo.get_history.return_value = []

        history = await manager.get_history()
        assert history == []

    async def test_custom_limit(self, manager, mock_repo):
        """get_history() should pass limit to repo."""
        mock_repo.get_history.return_value = []

        await manager.get_history(limit=5)
        mock_repo.get_history.assert_awaited_once_with(limit=5)
