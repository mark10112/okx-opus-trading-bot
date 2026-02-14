"""News schedule for FOMC/CPI/NFP + trigger logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
        now = datetime.now(timezone.utc)
        for event in self.events:
            time_until = (event.scheduled_at - now).total_seconds()
            if 0 <= time_until <= minutes_before * 60:
                logger.info(
                    "news_window_active",
                    event_name=event.name,
                    minutes_until=time_until / 60,
                )
                return True
        return False

    def get_upcoming_events(self, hours: int = 24) -> list[ScheduledEvent]:
        """Get events in the next N hours."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours)
        upcoming = [e for e in self.events if now < e.scheduled_at <= cutoff]
        return sorted(upcoming, key=lambda e: e.scheduled_at)

    def load_events_from_config(self) -> None:
        """Load hardcoded 2026 schedule + any dynamic events."""
        # 2026 FOMC meeting dates (announcement day, 14:00 ET = 18:00 UTC)
        fomc_dates = [
            (1, 28), (3, 18), (5, 6), (6, 17),
            (7, 29), (9, 16), (11, 4), (12, 16),
        ]
        for month, day in fomc_dates:
            self.events.append(
                ScheduledEvent(
                    name="FOMC Rate Decision",
                    scheduled_at=datetime(2026, month, day, 18, 0, tzinfo=timezone.utc),
                    impact="high",
                )
            )

        # 2026 CPI release dates (typically 2nd week, 08:30 ET = 12:30 UTC)
        cpi_dates = [
            (1, 13), (2, 11), (3, 11), (4, 14),
            (5, 12), (6, 10), (7, 14), (8, 12),
            (9, 15), (10, 13), (11, 10), (12, 10),
        ]
        for month, day in cpi_dates:
            self.events.append(
                ScheduledEvent(
                    name="CPI Release",
                    scheduled_at=datetime(2026, month, day, 12, 30, tzinfo=timezone.utc),
                    impact="high",
                )
            )

        # 2026 NFP release dates (first Friday, 08:30 ET = 12:30 UTC)
        nfp_dates = [
            (1, 9), (2, 6), (3, 6), (4, 3),
            (5, 8), (6, 5), (7, 2), (8, 7),
            (9, 4), (10, 2), (11, 6), (12, 4),
        ]
        for month, day in nfp_dates:
            self.events.append(
                ScheduledEvent(
                    name="NFP Employment Report",
                    scheduled_at=datetime(2026, month, day, 12, 30, tzinfo=timezone.utc),
                    impact="high",
                )
            )

        # 2026 GDP release dates (quarterly, 08:30 ET = 12:30 UTC)
        gdp_dates = [
            (1, 29), (4, 29), (7, 29), (10, 29),
        ]
        for month, day in gdp_dates:
            self.events.append(
                ScheduledEvent(
                    name="GDP Report",
                    scheduled_at=datetime(2026, month, day, 12, 30, tzinfo=timezone.utc),
                    impact="high",
                )
            )

        logger.info("news_events_loaded", count=len(self.events))
