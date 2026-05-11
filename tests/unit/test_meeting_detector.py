"""Tests for app.ai.meeting_detector with mocked Claude client."""

import json
from unittest.mock import MagicMock, patch

from app.ai import meeting_detector
from app.database import db


def _make_response(text: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


def _meeting_payload(**overrides) -> str:
    base = {
        "is_meeting": True,
        "title": "Sync with Alice",
        "proposed_datetime": "2026-05-19T15:00:00Z",
        "duration_minutes": 30,
        "participants": ["alice@example.com"],
        "location": "Zoom",
        "confidence": 0.92,
        "notes": None,
    }
    base.update(overrides)
    return json.dumps(base)


@patch.object(meeting_detector, "_get_client")
def test_detect_meeting_parses_valid_json(mock_get_client):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_response(_meeting_payload())
    mock_get_client.return_value = mock_client

    result = meeting_detector.detect_meeting(
        {"sender": "alice@example.com", "subject": "Sync", "body": "let's meet"}
    )

    assert result["is_meeting"] is True
    assert result["proposed_datetime"] == "2026-05-19T15:00:00Z"
    assert result["confidence"] == 0.92
    assert result["participants"] == ["alice@example.com"]


@patch.object(meeting_detector, "_get_client")
def test_detect_meeting_strips_markdown_fences(mock_get_client):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_response(
        "```json\n" + _meeting_payload(is_meeting=False, confidence=0.05) + "\n```"
    )
    mock_get_client.return_value = mock_client

    result = meeting_detector.detect_meeting({"sender": "n@n", "subject": "FYI", "body": ""})
    assert result["is_meeting"] is False


@patch.object(meeting_detector, "_get_client")
def test_detect_meeting_returns_none_on_invalid_json(mock_get_client):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_response("not json")
    mock_get_client.return_value = mock_client

    assert meeting_detector.detect_meeting({"sender": "a", "subject": "s", "body": ""}) is None


@patch.object(meeting_detector, "_get_client")
def test_detect_meeting_returns_none_on_api_error(mock_get_client):
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = RuntimeError("API down")
    mock_get_client.return_value = mock_client

    assert meeting_detector.detect_meeting({"sender": "a", "subject": "s", "body": ""}) is None


@patch.object(meeting_detector, "_get_client")
def test_detect_meeting_normalizes_participants_to_list(mock_get_client):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_response(_meeting_payload(participants=None))
    mock_get_client.return_value = mock_client

    result = meeting_detector.detect_meeting({"sender": "a", "subject": "s", "body": ""})
    assert result["participants"] == []


@patch.object(meeting_detector, "_get_client")
def test_detect_meeting_anchors_prompt_on_received_date(mock_get_client):
    captured = {}

    def fake_create(**kwargs):
        captured["prompt"] = kwargs["messages"][0]["content"]
        return _make_response(_meeting_payload())

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = fake_create
    mock_get_client.return_value = mock_client

    meeting_detector.detect_meeting(
        {
            "sender": "a@a",
            "subject": "s",
            "body": "next Tuesday at 3pm",
            "received_date": "Mon, 10 May 2026 09:00:00 +0000",
        }
    )
    assert "Mon, 10 May 2026 09:00:00 +0000" in captured["prompt"]


def test_split_iso_datetime_handles_full_value():
    assert meeting_detector._split_iso_datetime("2026-05-19T15:00:00Z") == (
        "2026-05-19",
        "15:00:00",
    )


def test_split_iso_datetime_handles_date_only():
    assert meeting_detector._split_iso_datetime("2026-05-19") == ("2026-05-19", None)


def test_split_iso_datetime_handles_none_and_garbage():
    assert meeting_detector._split_iso_datetime(None) == (None, None)
    assert meeting_detector._split_iso_datetime("") == (None, None)
    assert meeting_detector._split_iso_datetime(123) == (None, None)


def _insert_email(gmail_id: str = "mt_one") -> int:
    return db.insert_email(
        {
            "id": gmail_id,
            "thread_id": "t",
            "sender": "alice@example.com",
            "subject": "Sync request",
            "body": "let's meet next Tuesday",
            "snippet": "",
            "date": "Mon, 10 May 2026 09:00:00 +0000",
        }
    )


def _email_row(email_row_id: int) -> dict:
    row = db.get_email_by_row_id(email_row_id)
    assert row is not None
    return row


@patch.object(meeting_detector, "_get_client")
def test_maybe_detect_meeting_persists_when_schedule_and_confident(mock_get_client):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_response(_meeting_payload())
    mock_get_client.return_value = mock_client

    email_row_id = _insert_email("mt_persist")
    email = _email_row(email_row_id)

    new_id = meeting_detector.maybe_detect_meeting(email, {"action_required": "Schedule"})

    assert new_id is not None
    events = db.get_calendar_event_by_email(email_row_id)
    assert len(events) == 1
    ev = events[0]
    assert ev["title"] == "Sync with Alice"
    assert ev["event_date"] == "2026-05-19"
    assert ev["event_time"] == "15:00:00"
    assert ev["duration_minutes"] == 30
    assert ev["participants"] == "alice@example.com"
    assert ev["location"] == "Zoom"
    assert ev["status"] == "detected"


@patch.object(meeting_detector, "_get_client")
def test_maybe_detect_meeting_skips_when_action_not_schedule(mock_get_client):
    email_row_id = _insert_email("mt_skip_action")
    email = _email_row(email_row_id)

    new_id = meeting_detector.maybe_detect_meeting(email, {"action_required": "Reply"})

    assert new_id is None
    assert db.get_calendar_event_by_email(email_row_id) == []
    mock_get_client.assert_not_called()


@patch.object(meeting_detector, "_get_client")
def test_maybe_detect_meeting_skips_low_confidence(mock_get_client):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_response(
        _meeting_payload(confidence=0.3, proposed_datetime=None, notes="ambiguous")
    )
    mock_get_client.return_value = mock_client

    email_row_id = _insert_email("mt_low_conf")
    email = _email_row(email_row_id)

    new_id = meeting_detector.maybe_detect_meeting(email, {"action_required": "Schedule"})

    assert new_id is None
    assert db.get_calendar_event_by_email(email_row_id) == []


@patch.object(meeting_detector, "_get_client")
def test_maybe_detect_meeting_skips_when_not_meeting(mock_get_client):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_response(
        _meeting_payload(is_meeting=False, confidence=0.95)
    )
    mock_get_client.return_value = mock_client

    email_row_id = _insert_email("mt_not_meeting")
    email = _email_row(email_row_id)

    new_id = meeting_detector.maybe_detect_meeting(email, {"action_required": "Schedule"})

    assert new_id is None
    assert db.get_calendar_event_by_email(email_row_id) == []


@patch.object(meeting_detector, "_get_client")
def test_maybe_detect_meeting_is_idempotent(mock_get_client):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_response(_meeting_payload())
    mock_get_client.return_value = mock_client

    email_row_id = _insert_email("mt_idempotent")
    email = _email_row(email_row_id)

    first_id = meeting_detector.maybe_detect_meeting(email, {"action_required": "Schedule"})
    second_id = meeting_detector.maybe_detect_meeting(email, {"action_required": "Schedule"})

    assert first_id is not None
    assert second_id is None
    # Detector should not have been invoked the second time (existing row short-circuits).
    assert mock_client.messages.create.call_count == 1
    assert len(db.get_calendar_event_by_email(email_row_id)) == 1


@patch.object(meeting_detector, "_get_client")
def test_maybe_detect_meeting_handles_detector_returning_none(mock_get_client):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_response("not json")
    mock_get_client.return_value = mock_client

    email_row_id = _insert_email("mt_none")
    email = _email_row(email_row_id)

    new_id = meeting_detector.maybe_detect_meeting(email, {"action_required": "Schedule"})

    assert new_id is None
    assert db.get_calendar_event_by_email(email_row_id) == []


@patch.object(meeting_detector, "_get_client")
def test_maybe_detect_meeting_falls_back_to_subject_when_title_missing(mock_get_client):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_response(_meeting_payload(title=None))
    mock_get_client.return_value = mock_client

    email_row_id = _insert_email("mt_no_title")
    email = _email_row(email_row_id)

    new_id = meeting_detector.maybe_detect_meeting(email, {"action_required": "Schedule"})

    assert new_id is not None
    ev = db.get_calendar_event_by_email(email_row_id)[0]
    assert ev["title"] == "Sync request"
