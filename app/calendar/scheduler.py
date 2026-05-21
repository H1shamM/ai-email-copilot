"""Turn a detected `calendar_events` row into a real Google Calendar event.

Testable orchestration over `app.calendar.service` (live API) + `app.database.db`,
mirroring how `app.ai.meeting_detector.maybe_detect_meeting` composes the lower
layers. The live I/O stays behind `service.py`; everything here is unit-tested by
mocking `service.check_busy` / `service.insert_event`.
"""

from datetime import datetime, timedelta, timezone

from app.calendar import service

DEFAULT_DURATION_MINUTES = 30


def event_window(event_row: dict) -> tuple[str, str] | None:
    """Compute (start, end) as RFC3339 UTC for a detected event row.

    Combines `event_date` + `event_time`; the end is `DEFAULT_DURATION_MINUTES`
    after the start when `duration_minutes` is null. Returns None when the row
    has no concrete date+time, so undated detections can't be scheduled.
    """
    event_date = event_row.get("event_date")
    event_time = event_row.get("event_time")
    if not event_date or not event_time:
        return None

    try:
        start = datetime.fromisoformat(f"{event_date}T{event_time}")
    except ValueError:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    duration = event_row.get("duration_minutes") or DEFAULT_DURATION_MINUTES
    end = start + timedelta(minutes=duration)
    return _to_rfc3339(start), _to_rfc3339(end)


def _to_rfc3339(value: datetime) -> str:
    """Format a tz-aware datetime as RFC3339 UTC with a trailing Z."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_event_body(event_row: dict) -> dict:
    """Build the Google Calendar event resource from a detected event row.

    Omits `location`/`attendees` rather than sending nulls so the API receives a
    clean body. Raises ValueError if the row has no schedulable date+time.
    """
    window = event_window(event_row)
    if window is None:
        raise ValueError("event_row has no schedulable date/time")
    start, end = window

    body: dict = {
        "summary": event_row.get("title") or "Untitled meeting",
        "start": {"dateTime": start, "timeZone": "UTC"},
        "end": {"dateTime": end, "timeZone": "UTC"},
    }
    if event_row.get("location"):
        body["location"] = event_row["location"]

    attendees = _parse_participants(event_row.get("participants"))
    if attendees:
        body["attendees"] = [{"email": email} for email in attendees]

    return body


def _parse_participants(participants: str | None) -> list[str]:
    """Split the comma-joined participants string into a clean list of emails."""
    if not participants:
        return []
    return [p.strip() for p in participants.split(",") if p.strip()]


def has_conflict(event_row: dict) -> bool:
    """True if the event's window overlaps any busy interval on the calendar."""
    window = event_window(event_row)
    if window is None:
        return False
    start, end = window
    return bool(service.check_busy(start, end))


def create_event(event_row: dict) -> str:
    """Insert the event on the primary calendar; return the Google event id."""
    body = build_event_body(event_row)
    created = service.insert_event(body)
    return created["id"]
