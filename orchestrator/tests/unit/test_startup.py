"""Tests for startup initialization — wiring + default playbook."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestStartupWiring:
    """Test that orchestrator main wires all components correctly."""

    def test_orchestrator_accepts_dependencies(self):
        """Orchestrator can receive all injected dependencies."""
        from orchestrator.state_machine import Orchestrator

        settings = MagicMock()
        redis = AsyncMock()
        orch = Orchestrator(settings=settings, redis=redis)

        # Verify dependency injection slots exist
        assert hasattr(orch, "trade_repo")
        assert hasattr(orch, "playbook_manager")
        assert hasattr(orch, "risk_gate")
        assert hasattr(orch, "haiku_screener")
        assert hasattr(orch, "opus_client")
        assert hasattr(orch, "perplexity_client")
        assert hasattr(orch, "reflection_engine")
        assert hasattr(orch, "prompt_builder")

    def test_snapshot_scheduler_accepts_repos(self):
        """SnapshotScheduler can be created with repos."""
        from orchestrator.snapshot_scheduler import SnapshotScheduler

        scheduler = SnapshotScheduler(
            trade_repo=AsyncMock(),
            snapshot_repo=AsyncMock(),
        )
        assert scheduler.trade_repo is not None
        assert scheduler.snapshot_repo is not None


class TestDefaultPlaybook:
    """Test default playbook initialization on startup."""

    @pytest.mark.asyncio
    async def test_get_latest_creates_default_if_empty(self):
        """PlaybookManager.get_latest() creates default playbook if DB is empty."""
        from orchestrator.playbook_manager import PlaybookManager

        playbook_repo = AsyncMock()
        playbook_repo.get_latest.return_value = None
        playbook_repo.save_version.return_value = 1

        mgr = PlaybookManager(playbook_repo)
        playbook = await mgr.get_latest()

        assert playbook is not None
        assert playbook.version >= 1
        # Should have saved the default
        playbook_repo.save_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_latest_returns_existing(self):
        """PlaybookManager.get_latest() returns existing playbook from DB."""
        from orchestrator.models.playbook import Playbook
        from orchestrator.playbook_manager import PlaybookManager

        existing_playbook = Playbook(version=5)
        stored = {"playbook_json": existing_playbook.model_dump(mode="json")}
        playbook_repo = AsyncMock()
        playbook_repo.get_latest.return_value = stored

        mgr = PlaybookManager(playbook_repo)
        playbook = await mgr.get_latest()

        assert playbook.version == 5
        # Should NOT save a new default
        playbook_repo.save_version.assert_not_called()


class TestSessionFactoryWiring:
    """Test DB engine → session factory → repository wiring."""

    def test_create_session_factory(self):
        """create_session_factory returns a callable sessionmaker."""
        from orchestrator.db.engine import create_db_engine, create_session_factory

        engine = create_db_engine("postgresql+asyncpg://localhost/test")
        factory = create_session_factory(engine)
        assert callable(factory)
        engine.sync_engine.dispose()

    def test_repository_accepts_session_factory(self):
        """TradeRepository can be created with a session factory."""
        from orchestrator.db.repository import TradeRepository

        factory = AsyncMock()
        repo = TradeRepository(factory)
        assert repo.session_factory is factory

    def test_all_repositories_accept_session_factory(self):
        """All repositories can be created with a session factory."""
        from orchestrator.db.repository import (
            PerformanceSnapshotRepository,
            PlaybookRepository,
            ReflectionRepository,
            ResearchCacheRepository,
            RiskRejectionRepository,
            ScreenerLogRepository,
            TradeRepository,
        )

        factory = AsyncMock()
        repos = [
            TradeRepository(factory),
            PlaybookRepository(factory),
            ReflectionRepository(factory),
            ScreenerLogRepository(factory),
            ResearchCacheRepository(factory),
            RiskRejectionRepository(factory),
            PerformanceSnapshotRepository(factory),
        ]
        for repo in repos:
            assert repo.session_factory is factory
