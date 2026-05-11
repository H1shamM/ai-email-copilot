"""Thin wrappers around Google Calendar API (events + freebusy).

Mirrors app/gmail/service.py: a lazy singleton service builder plus
small wrappers that the rest of the app composes against.
"""

from googleapiclient.discovery import build

from app.gmail.auth import get_credentials

_service = None


def get_calendar_service():  # pragma: no cover
    """Lazy singleton: build the Calendar discovery client once and cache it."""
    global _service
    if _service is None:
        credentials = get_credentials()
        _service = build("calendar", "v3", credentials=credentials)
    return _service


def reset_service_cache() -> None:
    """Drop the cached service handle (used by tests to inject a fake)."""
    global _service
    _service = None


def insert_event(event: dict, calendar_id: str = "primary") -> dict:
    """Create an event on the given calendar; returns the inserted event resource."""
    service = get_calendar_service()
    return service.events().insert(calendarId=calendar_id, body=event).execute()


def list_events(
    time_min: str,
    time_max: str,
    calendar_id: str = "primary",
    max_results: int = 50,
) -> list[dict]:
    """List events between two RFC3339 timestamps, ordered by start time."""
    service = get_calendar_service()
    response = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return response.get("items", [])


def check_busy(
    time_min: str,
    time_max: str,
    calendar_id: str = "primary",
) -> list[dict]:
    """Return busy intervals for the calendar in [time_min, time_max].

    Each item is `{"start": rfc3339, "end": rfc3339}` from the Calendar API's
    freebusy.query response — empty list means the window is free.
    """
    service = get_calendar_service()
    response = (
        service.freebusy()
        .query(
            body={
                "timeMin": time_min,
                "timeMax": time_max,
                "items": [{"id": calendar_id}],
            }
        )
        .execute()
    )
    return response.get("calendars", {}).get(calendar_id, {}).get("busy", [])
