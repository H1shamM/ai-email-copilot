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


def test_event_window_interprets_time_in_user_timezone(monkeypatch):
    """A 15:00 wall-clock time in a UTC+3 zone is the 12:00Z absolute instant."""
    monkeypatch.setenv("USER_TIMEZONE", "Etc/GMT-3")  # fixed UTC+3, no DST
    start, end = scheduler.event_window(_row())
    assert start == "2026-05-19T12:00:00Z"
    assert end == "2026-05-19T13:00:00Z"


def test_event_window_unknown_timezone_falls_back_to_utc(monkeypatch):
    monkeypatch.setenv("USER_TIMEZONE", "Not/AZone")
    start, _ = scheduler.event_window(_row())
    assert start == "2026-05-19T15:00:00Z"


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


def test_build_event_body_attaches_summary_and_thread_link():
    email = {"ai_summary": "Alice wants to sync on Q3.", "thread_id": "abc123"}
    body = scheduler.build_event_body(_row(), email)
    assert "Alice wants to sync on Q3." in body["description"]
    assert "https://mail.google.com/mail/u/0/#all/abc123" in body["description"]


def test_build_event_body_description_summary_only_when_no_thread():
    email = {"ai_summary": "Quick chat.", "thread_id": None}
    body = scheduler.build_event_body(_row(), email)
    assert body["description"] == "Quick chat."
    assert "mail.google.com" not in body["description"]


def test_build_event_body_omits_description_without_email():
    assert "description" not in scheduler.build_event_body(_row())


def test_build_event_body_omits_description_when_email_empty():
    email = {"ai_summary": None, "thread_id": None}
    assert "description" not in scheduler.build_event_body(_row(), email)


def test_build_description_link_only_when_no_summary():
    desc = scheduler.build_description({"ai_summary": "", "thread_id": "t9"})
    assert desc == "📧 Source thread: https://mail.google.com/mail/u/0/#all/t9"


def test_build_description_none_for_none_email():
    assert scheduler.build_description(None) is None


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
