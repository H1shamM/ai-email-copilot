"""Integration tests against the real Google Calendar API.

Run with: pytest -m integration tests/integration/test_calendar_integration.py
"""

import os
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.path.exists("token.pickle"),
        reason="Requires authenticated token.pickle (re-auth after Calendar scope added)",
    ),
]


def _rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_list_events_next_24h_returns_list():
    """Live Calendar call returns a list (possibly empty) for the next 24h window."""
    from app.calendar.service import list_events

    now = datetime.now(timezone.utc)
    events = list_events(_rfc3339(now), _rfc3339(now + timedelta(days=1)))
    assert isinstance(events, list)


def test_check_busy_next_24h_returns_list():
    """freebusy.query returns a list of busy intervals (possibly empty) for the next 24h."""
    from app.calendar.service import check_busy

    now = datetime.now(timezone.utc)
    busy = check_busy(_rfc3339(now), _rfc3339(now + timedelta(days=1)))
    assert isinstance(busy, list)
    for interval in busy:
        assert "start" in interval
        assert "end" in interval
