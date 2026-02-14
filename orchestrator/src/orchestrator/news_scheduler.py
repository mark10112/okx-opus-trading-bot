"""News schedule for FOMC/CPI/NFP + trigger logic."""

from __future__ import annotations

from datetime import datetime

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class ScheduledEvent(BaseModel):
    name: str
    scheduled_at: datetime
    impact: str  # high, medium, low
    currency: str = "USD"


class NewsScheduler:
    """
    Check if near important news events:
    - FOMC meetings
    - CPI releases
    - NFP (Non-Farm Payrolls)
    - GDP reports
    - Fed speeches
    """

    def __init__(self) -> None:
        self.events: list[ScheduledEvent] = []
        self.load_events_from_config()

    def is_news_window(self, minutes_before: int = 30) -> bool:
        """Return True if within N minutes before an important news event."""
        ...

    def get_upcoming_events(self, hours: int = 24) -> list[ScheduledEvent]:
        """Get events in the next N hours."""
        ...

    def load_events_from_config(self) -> None:
        """Load hardcoded 2026 schedule + any dynamic events."""
        ...
