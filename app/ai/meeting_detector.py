"""Detect meeting requests in emails and persist them as calendar_events rows.

Mirrors app/ai/analyzer.py: lazy Anthropic client, prompt as module constant,
JSON-only response, returns None on parse/API failure. Persistence wrapper is
idempotent so the same email can be re-analyzed without duplicating rows.
"""

import json
import logging
import os

from anthropic import Anthropic

from app.ai import MODEL
from app.database import db

logger = logging.getLogger(__name__)

_client = None

CONFIDENCE_THRESHOLD = 0.6

# A meeting request reliably lands in only these analyzer actions — "needs a reply"
# and "is a meeting" aren't mutually exclusive, so gating on "Schedule" alone drops
# real invites. Read/Archive/Flag stay excluded to bound the extra detector calls.
SCHEDULABLE_ACTIONS = {"Schedule", "Reply"}

MEETING_PROMPT = """Extract meeting/event details from this email and respond with JSON.

EMAIL:
From: {sender}
Subject: {subject}
Received: {received}
Body: {body}

Resolve any natural-language dates (e.g. "next Tuesday at 3pm") against the
Received date above. Always return ISO-8601 UTC for proposed_datetime, or null
if no date can be confidently extracted. If the email is NOT a meeting/event
request (e.g. it's a newsletter, FYI, or pure information), set is_meeting=false.

Respond ONLY with valid JSON (no markdown fences):
{{
  "is_meeting": true|false,
  "title": "short event title or null",
  "proposed_datetime": "YYYY-MM-DDTHH:MM:SSZ or null",
  "duration_minutes": integer or null,
  "participants": ["email1@x.com", ...],
  "location": "Zoom URL, physical address, or null",
  "confidence": 0.0-1.0,
  "notes": "any ambiguity or caveat, or null"
}}"""


def _get_client():
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def detect_meeting(email_data: dict) -> dict | None:
    """Ask Claude to extract structured meeting fields from an email."""
    prompt = MEETING_PROMPT.format(
        sender=email_data.get("sender", "Unknown"),
        subject=email_data.get("subject", "No subject"),
        received=email_data.get("received_date") or email_data.get("date") or "Unknown",
        body=email_data.get("body") or email_data.get("snippet", ""),
    )

    try:
        message = _get_client().messages.create(
            model=MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text.strip()

        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        parsed = json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse meeting JSON: %s", e)
        return None
    except Exception:
        logger.exception("Claude API error in detect_meeting")
        return None

    participants = parsed.get("participants") or []
    if not isinstance(participants, list):
        participants = []
    parsed["participants"] = participants
    return parsed


def _split_iso_datetime(iso: str | None) -> tuple[str | None, str | None]:
    """Split an ISO-8601 datetime into (YYYY-MM-DD, HH:MM:SS) parts.

    Returns (None, None) when the input is missing or unparseable so callers
    can write null event_date/event_time rather than crash on a bad model response.
    """
    if not iso or not isinstance(iso, str):
        return None, None
    cleaned = iso.replace("Z", "").strip()
    if "T" not in cleaned:
        return cleaned or None, None
    date_part, _, time_part = cleaned.partition("T")
    return (date_part or None), (time_part or None)


def maybe_detect_meeting(email_row: dict, analysis: dict) -> int | None:
    """Run the detector when analysis says Schedule, persist a row, return its id.

    Idempotent: skips work if `calendar_events` already has a row for this email.
    Returns the new event row id, or None if nothing was persisted (not a meeting,
    low confidence, detector failure, or already detected).
    """
    if analysis.get("action_required") not in SCHEDULABLE_ACTIONS:
        return None
    if db.get_calendar_event_by_email(email_row["id"]):
        return None

    meeting = detect_meeting(email_row)
    if not meeting or not meeting.get("is_meeting"):
        return None
    confidence = meeting.get("confidence") or 0.0
    if confidence < CONFIDENCE_THRESHOLD:
        return None

    event_date, event_time = _split_iso_datetime(meeting.get("proposed_datetime"))
    participants = ", ".join(meeting.get("participants") or []) or None

    return db.insert_calendar_event(
        email_id=email_row["id"],
        title=meeting.get("title") or (email_row.get("subject") or "Untitled meeting"),
        event_date=event_date,
        event_time=event_time,
        duration_minutes=meeting.get("duration_minutes"),
        participants=participants,
        location=meeting.get("location"),
        status="detected",
    )
