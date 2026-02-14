"""Unit tests for NewsScheduler — hardcoded 2026 schedule + time logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from orchestrator.news_scheduler import NewsScheduler, ScheduledEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def scheduler():
    return NewsScheduler()


# ---------------------------------------------------------------------------
# load_events_from_config()
# ---------------------------------------------------------------------------


class TestLoadEventsFromConfig:
    def test_loads_events(self, scheduler):
        """load_events_from_config() should populate events list."""
        assert len(scheduler.events) > 0

    def test_has_fomc_events(self, scheduler):
        """Should include FOMC meeting dates."""
        fomc = [e for e in scheduler.events if "FOMC" in e.name]
        assert len(fomc) >= 8  # 8 FOMC meetings per year

    def test_has_cpi_events(self, scheduler):
        """Should include CPI release dates."""
        cpi = [e for e in scheduler.events if "CPI" in e.name]
        assert len(cpi) >= 12  # monthly

    def test_has_nfp_events(self, scheduler):
        """Should include NFP release dates."""
        nfp = [e for e in scheduler.events if "NFP" in e.name]
        assert len(nfp) >= 12  # monthly

    def test_has_gdp_events(self, scheduler):
        """Should include GDP release dates."""
        gdp = [e for e in scheduler.events if "GDP" in e.name]
        assert len(gdp) >= 4  # quarterly

    def test_all_events_are_2026(self, scheduler):
        """All events should be in 2026."""
        for event in scheduler.events:
            assert event.scheduled_at.year == 2026

    def test_all_events_utc(self, scheduler):
        """All events should have UTC timezone."""
        for event in scheduler.events:
            assert event.scheduled_at.tzinfo is not None

    def test_all_high_impact(self, scheduler):
        """All hardcoded events should be high impact."""
        for event in scheduler.events:
            assert event.impact == "high"


# ---------------------------------------------------------------------------
# is_news_window()
# ---------------------------------------------------------------------------


class TestIsNewsWindow:
    def test_within_window_returns_true(self, scheduler):
        """Should return True when within N minutes before an event."""
        # Place a fake event 15 minutes from now
        now = datetime.now(timezone.utc)
        scheduler.events = [
            ScheduledEvent(
                name="Test Event",
                scheduled_at=now + timedelta(minutes=15),
                impact="high",
            )
        ]
        assert scheduler.is_news_window(minutes_before=30) is True

    def test_outside_window_returns_false(self, scheduler):
        """Should return False when outside the window."""
        now = datetime.now(timezone.utc)
        scheduler.events = [
            ScheduledEvent(
                name="Test Event",
                scheduled_at=now + timedelta(hours=2),
                impact="high",
            )
        ]
        assert scheduler.is_news_window(minutes_before=30) is False

    def test_after_event_returns_false(self, scheduler):
        """Should return False when event has already passed."""
        now = datetime.now(timezone.utc)
        scheduler.events = [
            ScheduledEvent(
                name="Past Event",
                scheduled_at=now - timedelta(hours=1),
                impact="high",
            )
        ]
        assert scheduler.is_news_window(minutes_before=30) is False

    def test_exactly_at_boundary(self, scheduler):
        """Should return True when exactly at the window boundary."""
        now = datetime.now(timezone.utc)
        scheduler.events = [
            ScheduledEvent(
                name="Boundary Event",
                scheduled_at=now + timedelta(minutes=30),
                impact="high",
            )
        ]
        assert scheduler.is_news_window(minutes_before=30) is True

    def test_custom_window_size(self, scheduler):
        """Should respect custom minutes_before parameter."""
        now = datetime.now(timezone.utc)
        scheduler.events = [
            ScheduledEvent(
                name="Test Event",
                scheduled_at=now + timedelta(minutes=50),
                impact="high",
            )
        ]
        assert scheduler.is_news_window(minutes_before=30) is False
        assert scheduler.is_news_window(minutes_before=60) is True

    def test_empty_events_returns_false(self, scheduler):
        """Should return False when no events loaded."""
        scheduler.events = []
        assert scheduler.is_news_window(minutes_before=30) is False


# ---------------------------------------------------------------------------
# get_upcoming_events()
# ---------------------------------------------------------------------------


class TestGetUpcomingEvents:
    def test_filters_by_hours(self, scheduler):
        """Should return only events within N hours."""
        now = datetime.now(timezone.utc)
        scheduler.events = [
            ScheduledEvent(
                name="Soon",
                scheduled_at=now + timedelta(hours=2),
                impact="high",
            ),
            ScheduledEvent(
                name="Later",
                scheduled_at=now + timedelta(hours=48),
                impact="high",
            ),
        ]
        upcoming = scheduler.get_upcoming_events(hours=24)
        assert len(upcoming) == 1
        assert upcoming[0].name == "Soon"

    def test_excludes_past_events(self, scheduler):
        """Should not return events that have already passed."""
        now = datetime.now(timezone.utc)
        scheduler.events = [
            ScheduledEvent(
                name="Past",
                scheduled_at=now - timedelta(hours=1),
                impact="high",
            ),
            ScheduledEvent(
                name="Future",
                scheduled_at=now + timedelta(hours=5),
                impact="high",
            ),
        ]
        upcoming = scheduler.get_upcoming_events(hours=24)
        assert len(upcoming) == 1
        assert upcoming[0].name == "Future"

    def test_empty_when_no_upcoming(self, scheduler):
        """Should return empty list when no upcoming events."""
        now = datetime.now(timezone.utc)
        scheduler.events = [
            ScheduledEvent(
                name="Far Future",
                scheduled_at=now + timedelta(days=30),
                impact="high",
            ),
        ]
        upcoming = scheduler.get_upcoming_events(hours=24)
        assert upcoming == []

    def test_default_24_hours(self, scheduler):
        """Default window should be 24 hours."""
        now = datetime.now(timezone.utc)
        scheduler.events = [
            ScheduledEvent(
                name="Tomorrow",
                scheduled_at=now + timedelta(hours=23),
                impact="high",
            ),
        ]
        upcoming = scheduler.get_upcoming_events()
        assert len(upcoming) == 1

    def test_sorted_by_time(self, scheduler):
        """Upcoming events should be sorted by scheduled_at."""
        now = datetime.now(timezone.utc)
        scheduler.events = [
            ScheduledEvent(
                name="Second",
                scheduled_at=now + timedelta(hours=10),
                impact="high",
            ),
            ScheduledEvent(
                name="First",
                scheduled_at=now + timedelta(hours=2),
                impact="high",
            ),
        ]
        upcoming = scheduler.get_upcoming_events(hours=24)
        assert len(upcoming) == 2
        assert upcoming[0].name == "First"
        assert upcoming[1].name == "Second"
