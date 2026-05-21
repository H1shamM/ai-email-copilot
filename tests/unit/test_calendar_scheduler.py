"""Unit tests for app.calendar.scheduler (no live Calendar calls)."""

import pytest

from app.calendar import scheduler


def _row(**overrides) -> dict:
    """A detected calendar_events row with sensible defaults, overridable per test."""
    base = {
        "id": 1,
        "title": "Sync with Alice",
        "event_date": "2026-05-19",
        "event_time": "15:00:00",
        "duration_minutes": 60,
        "participants": "alice@x.com, bob@y.com",
        "location": "Zoom",
        "status": "detected",
    }
    base.update(overrides)
    return base


def test_event_window_full_row():
    start, end = scheduler.event_window(_row())
    assert start == "2026-05-19T15:00:00Z"
    assert end == "2026-05-19T16:00:00Z"


def test_event_window_defaults_duration_when_null():
    start, end = scheduler.event_window(_row(duration_minutes=None))
    assert start == "2026-05-19T15:00:00Z"
    assert end == "2026-05-19T15:30:00Z"  # DEFAULT_DURATION_MINUTES = 30


def test_event_window_none_without_date_or_time():
    assert scheduler.event_window(_row(event_date=None)) is None
    assert scheduler.event_window(_row(event_time=None)) is None


def test_event_window_none_on_unparseable_datetime():
    assert scheduler.event_window(_row(event_time="not-a-time")) is None


def test_build_event_body_full_row():
    body = scheduler.build_event_body(_row())
    assert body["summary"] == "Sync with Alice"
    assert body["location"] == "Zoom"
    assert body["start"] == {"dateTime": "2026-05-19T15:00:00Z", "timeZone": "UTC"}
    assert body["end"] == {"dateTime": "2026-05-19T16:00:00Z", "timeZone": "UTC"}
    assert body["attendees"] == [{"email": "alice@x.com"}, {"email": "bob@y.com"}]


def test_build_event_body_omits_null_location_and_participants():
    body = scheduler.build_event_body(_row(location=None, participants=None))
    assert "location" not in body
    assert "attendees" not in body
    assert body["summary"] == "Sync with Alice"


def test_build_event_body_raises_without_window():
    with pytest.raises(ValueError, match="no schedulable date/time"):
        scheduler.build_event_body(_row(event_time=None))


def test_has_conflict_true_when_busy(monkeypatch):
    monkeypatch.setattr(
        scheduler.service,
        "check_busy",
        lambda *_a, **_k: [{"start": "2026-05-19T15:30:00Z", "end": "2026-05-19T16:00:00Z"}],
    )
    assert scheduler.has_conflict(_row()) is True


def test_has_conflict_false_when_free(monkeypatch):
    monkeypatch.setattr(scheduler.service, "check_busy", lambda *_a, **_k: [])
    assert scheduler.has_conflict(_row()) is False


def test_has_conflict_false_when_no_window(monkeypatch):
    called = False

    def _boom(*_a, **_k):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(scheduler.service, "check_busy", _boom)
    assert scheduler.has_conflict(_row(event_time=None)) is False
    assert called is False  # never queries freebusy for an undated row


def test_create_event_returns_google_event_id(monkeypatch):
    captured = {}

    def _fake_insert(body, *_a, **_k):
        captured["body"] = body
        return {"id": "goog_evt_99"}

    monkeypatch.setattr(scheduler.service, "insert_event", _fake_insert)
    assert scheduler.create_event(_row()) == "goog_evt_99"
    assert captured["body"]["summary"] == "Sync with Alice"
