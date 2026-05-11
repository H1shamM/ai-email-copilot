"""Unit tests for app.calendar.service wrappers (no live Calendar calls)."""

from unittest.mock import MagicMock

import pytest

from app.calendar import service as cal_service


@pytest.fixture(autouse=True)
def _reset_cache():
    """Ensure each test starts with no cached service handle."""
    cal_service.reset_service_cache()
    yield
    cal_service.reset_service_cache()


def _install_fake_service(monkeypatch) -> MagicMock:
    """Replace the cached Calendar service with a MagicMock so wrappers exercise it."""
    fake = MagicMock(name="calendar_service")
    monkeypatch.setattr(cal_service, "_service", fake)
    return fake


def test_insert_event_calls_events_insert(monkeypatch):
    fake = _install_fake_service(monkeypatch)
    expected = {"id": "evt_123", "summary": "Test"}
    fake.events.return_value.insert.return_value.execute.return_value = expected

    payload = {"summary": "Test", "start": {"dateTime": "2026-05-11T10:00:00Z"}}
    result = cal_service.insert_event(payload)

    assert result == expected
    fake.events.return_value.insert.assert_called_once_with(calendarId="primary", body=payload)


def test_insert_event_honors_calendar_id(monkeypatch):
    fake = _install_fake_service(monkeypatch)
    fake.events.return_value.insert.return_value.execute.return_value = {"id": "evt"}

    cal_service.insert_event({"summary": "x"}, calendar_id="work@group.calendar.google.com")

    fake.events.return_value.insert.assert_called_once_with(
        calendarId="work@group.calendar.google.com", body={"summary": "x"}
    )


def test_list_events_returns_items(monkeypatch):
    fake = _install_fake_service(monkeypatch)
    fake.events.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "a"}, {"id": "b"}]
    }

    items = cal_service.list_events("2026-05-10T00:00:00Z", "2026-05-11T00:00:00Z")

    assert items == [{"id": "a"}, {"id": "b"}]
    fake.events.return_value.list.assert_called_once_with(
        calendarId="primary",
        timeMin="2026-05-10T00:00:00Z",
        timeMax="2026-05-11T00:00:00Z",
        maxResults=50,
        singleEvents=True,
        orderBy="startTime",
    )


def test_list_events_returns_empty_when_no_items(monkeypatch):
    fake = _install_fake_service(monkeypatch)
    fake.events.return_value.list.return_value.execute.return_value = {}

    assert cal_service.list_events("a", "b") == []


def test_check_busy_returns_busy_intervals(monkeypatch):
    fake = _install_fake_service(monkeypatch)
    fake.freebusy.return_value.query.return_value.execute.return_value = {
        "calendars": {
            "primary": {"busy": [{"start": "2026-05-10T09:00:00Z", "end": "2026-05-10T10:00:00Z"}]}
        }
    }

    busy = cal_service.check_busy("2026-05-10T00:00:00Z", "2026-05-10T23:59:59Z")

    assert busy == [{"start": "2026-05-10T09:00:00Z", "end": "2026-05-10T10:00:00Z"}]
    fake.freebusy.return_value.query.assert_called_once_with(
        body={
            "timeMin": "2026-05-10T00:00:00Z",
            "timeMax": "2026-05-10T23:59:59Z",
            "items": [{"id": "primary"}],
        }
    )


def test_check_busy_returns_empty_when_calendar_missing(monkeypatch):
    fake = _install_fake_service(monkeypatch)
    fake.freebusy.return_value.query.return_value.execute.return_value = {"calendars": {}}

    assert cal_service.check_busy("a", "b") == []


def test_reset_service_cache_clears_state(monkeypatch):
    _install_fake_service(monkeypatch)
    assert cal_service._service is not None
    cal_service.reset_service_cache()
    assert cal_service._service is None
