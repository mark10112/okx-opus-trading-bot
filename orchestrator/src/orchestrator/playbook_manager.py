"""Playbook CRUD & versioning in DB."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from orchestrator.models.playbook import Playbook

logger = structlog.get_logger()


class PlaybookManager:
    def __init__(self, repo: object) -> None:
        self.repo = repo

    async def get_latest(self) -> Playbook:
        """Load latest playbook version from DB. Create default if none exists."""
        ...

    async def save_version(
        self,
        playbook: Playbook,
        change_summary: str,
        triggered_by: str,
        performance: dict,
    ) -> int:
        """Save new version, return version number."""
        ...

    async def get_version(self, version: int) -> Playbook:
        """Load specific version."""
        ...

    async def get_history(self, limit: int = 20) -> list:
        """Get version history with change summaries."""
        ...
