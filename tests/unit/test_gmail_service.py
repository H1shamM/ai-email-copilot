"""Unit tests for app.gmail.service helpers (no live Gmail calls)."""

import base64

from app.gmail.service import _get_header, _get_body, parse_email


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def test_get_header_case_insensitive():
    headers = [{"name": "From", "value": "alice@example.com"}]
    assert _get_header(headers, "from") == "alice@example.com"
    assert _get_header(headers, "missing") is None


def test_get_body_plain_text():
    payload = {"mimeType": "text/plain", "body": {"data": _b64("Hello world")}}
    assert _get_body(payload) == "Hello world"


def test_get_body_multipart():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/html", "body": {"data": _b64("<p>html</p>")}},
            {"mimeType": "text/plain", "body": {"data": _b64("plain text")}},
        ],
    }
    assert _get_body(payload) == "plain text"


def test_get_body_returns_none_when_missing():
    assert _get_body({"mimeType": "text/html", "body": {}}) is None


def test_parse_email_extracts_metadata():
    raw = {
        "id": "abc",
        "threadId": "thr",
        "snippet": "snip",
        "payload": {
            "mimeType": "text/plain",
            "body": {"data": _b64("hello")},
            "headers": [
                {"name": "From", "value": "a@a.com"},
                {"name": "Subject", "value": "Hi"},
                {"name": "Date", "value": "Wed, 15 Apr 2026"},
            ],
        },
    }
    parsed = parse_email(raw)
    assert parsed == {
        "id": "abc",
        "thread_id": "thr",
        "sender": "a@a.com",
        "subject": "Hi",
        "date": "Wed, 15 Apr 2026",
        "snippet": "snip",
        "body": "hello",
    }
