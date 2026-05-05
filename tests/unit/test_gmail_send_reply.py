"""Unit tests for the Gmail send_reply helpers (no live API calls)."""

import base64
from email import message_from_bytes

import pytest

from app.gmail.service import build_reply_mime, make_reply_envelope


def test_build_reply_mime_sets_headers_and_threading():
    raw = build_reply_mime(
        to="alice@example.com",
        subject="Re: Lunch",
        body="Sounds great.",
        in_reply_to="<orig@gmail.com>",
        references="<chain1@gmail.com>",
    )
    msg = message_from_bytes(raw)
    assert msg["To"] == "alice@example.com"
    assert msg["Subject"] == "Re: Lunch"
    assert msg["In-Reply-To"] == "<orig@gmail.com>"
    # References should chain previous + the message we're replying to
    assert msg["References"] == "<chain1@gmail.com> <orig@gmail.com>"
    assert "Sounds great." in msg.get_payload(decode=True).decode()


def test_build_reply_mime_no_in_reply_to_means_no_threading_headers():
    raw = build_reply_mime(
        to="a@b.com", subject="Hi", body="Body", in_reply_to=None, references=None
    )
    msg = message_from_bytes(raw)
    assert msg["In-Reply-To"] is None
    assert msg["References"] is None


def test_build_reply_mime_with_in_reply_to_only():
    """Original had no References — new References should equal In-Reply-To."""
    raw = build_reply_mime(
        to="a@b.com", subject="s", body="b", in_reply_to="<orig@x>", references=None
    )
    msg = message_from_bytes(raw)
    assert msg["References"] == "<orig@x>"


def test_make_reply_envelope_returns_thread_id_and_base64url_raw():
    headers = [
        {"name": "From", "value": "Alice <alice@example.com>"},
        {"name": "Subject", "value": "Hi"},
        {"name": "Message-ID", "value": "<abc@gmail.com>"},
    ]
    env = make_reply_envelope(headers, "thread-xyz", "Hello back")
    assert env["threadId"] == "thread-xyz"
    decoded = base64.urlsafe_b64decode(env["raw"].encode("ascii"))
    msg = message_from_bytes(decoded)
    assert msg["To"] == "Alice <alice@example.com>"
    assert msg["Subject"] == "Re: Hi"
    assert msg["In-Reply-To"] == "<abc@gmail.com>"


def test_make_reply_envelope_prefers_reply_to_header():
    headers = [
        {"name": "From", "value": "Alice <alice@example.com>"},
        {"name": "Reply-To", "value": "alice-list@example.com"},
        {"name": "Subject", "value": "Re: ongoing"},
    ]
    env = make_reply_envelope(headers, "t", "ok")
    decoded = base64.urlsafe_b64decode(env["raw"].encode("ascii"))
    msg = message_from_bytes(decoded)
    assert msg["To"] == "alice-list@example.com"


def test_make_reply_envelope_does_not_double_re_prefix():
    headers = [
        {"name": "From", "value": "x@x.com"},
        {"name": "Subject", "value": "Re: already"},
    ]
    env = make_reply_envelope(headers, "t", "b")
    decoded = base64.urlsafe_b64decode(env["raw"].encode("ascii"))
    msg = message_from_bytes(decoded)
    assert msg["Subject"] == "Re: already"


def test_make_reply_envelope_raises_without_addressable_header():
    with pytest.raises(ValueError, match="cannot reply"):
        make_reply_envelope([], "t", "b")
