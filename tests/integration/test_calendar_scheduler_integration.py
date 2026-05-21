"""Integration test for app.calendar.scheduler against the real Calendar API.

READ-ONLY: exercises the freebusy path via `has_conflict` for a window far in the
future. Never inserts/mutates the real calendar.

Run with: pytest -m integration tests/integration/test_calendar_scheduler_integration.py
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


def test_has_conflict_runs_freebusy_against_live_calendar():
    """has_conflict resolves the row's window and queries real freebusy, returning a bool."""
    from app.calendar import scheduler

    # A window ~1 year out at an unusual minute — almost certainly free, but we
    # only assert the call succeeds and returns a bool (no calendar mutation).
    far_future = datetime.now(timezone.utc) + timedelta(days=365)
    row = {
        "id": 0,
        "title": "Scheduler integration probe (read-only)",
        "event_date": far_future.strftime("%Y-%m-%d"),
        "event_time": "03:17:00",
        "duration_minutes": 15,
        "participants": None,
        "location": None,
    }
    assert isinstance(scheduler.has_conflict(row), bool)
