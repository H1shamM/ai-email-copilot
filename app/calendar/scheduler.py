"""Turn a detected `calendar_events` row into a real Google Calendar event.

Testable orchestration over `app.calendar.service` (live API) + `app.database.db`,
mirroring how `app.ai.meeting_detector.maybe_detect_meeting` composes the lower
layers. The live I/O stays behind `service.py`; everything here is unit-tested by
mocking `service.check_busy` / `service.insert_event`.
"""

from datetime import datetime, timedelta, timezone

from app.calendar import service

DEFAULT_DURATION_MINUTES = 30

_THREAD_URL = "https://mail.google.com/mail/u/0/#all/{thread_id}"


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


def build_description(email: dict | None) -> str | None:
    """Build the event description from the source email: AI summary + thread link.

    Returns None when neither a summary nor a thread link is available, so the
    caller can omit the `description` key entirely rather than send an empty one.
    """
    if not email:
        return None

    parts: list[str] = []
    summary = (email.get("ai_summary") or "").strip()
    if summary:
        parts.append(summary)

    thread_id = email.get("thread_id")
    if thread_id:
        parts.append(f"📧 Source thread: {_THREAD_URL.format(thread_id=thread_id)}")

    return "\n\n".join(parts) or None


def build_event_body(event_row: dict, email: dict | None = None) -> dict:
    """Build the Google Calendar event resource from a detected event row.

    Omits `location`/`attendees`/`description` rather than sending nulls so the API
    receives a clean body. When `email` is given, attaches its summary + a Gmail
    deep link as the event description. Raises ValueError if the row has no
    schedulable date+time.
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
        body["attendees"] = [{"email": email_addr} for email_addr in attendees]

    description = build_description(email)
    if description:
        body["description"] = description

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


def create_event(event_row: dict, email: dict | None = None) -> str:
    """Insert the event on the primary calendar; return the Google event id.

    `email` (the source email row) is threaded through so the booked event keeps
    a summary + link back to the originating conversation.
    """
    body = build_event_body(event_row, email)
    created = service.insert_event(body)
    return created["id"]
