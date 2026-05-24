"""Unit tests for no-reply sender detection (pure, no live API)."""

import pytest

from app.gmail.service import extract_email_address, is_no_reply_sender


@pytest.mark.parametrize(
    "sender,expected",
    [
        ("LinkedIn <messages-noreply@linkedin.com>", "messages-noreply@linkedin.com"),
        ("bob@example.com", "bob@example.com"),
        ("  Alice  <alice@example.com>  ", "alice@example.com"),
        (None, None),
        ("", None),
        ("Just A Name", "Just A Name"),
    ],
)
def test_extract_email_address(sender, expected):
    assert extract_email_address(sender) == expected


@pytest.mark.parametrize(
    "sender",
    [
        "LinkedIn <messages-noreply@linkedin.com>",
        "notifications-noreply@linkedin.com",
        "no-reply@github.com",
        "NoReply@Example.com",
        "donotreply@bank.com",
        "do-not-reply@service.io",
        "jobs-noreply@indeed.com",
    ],
)
def test_is_no_reply_sender_true_for_no_reply_addresses(sender):
    assert is_no_reply_sender(sender) is True


@pytest.mark.parametrize(
    "sender",
    [
        "Alice <alice@example.com>",
        "bob@example.com",
        "recruiter@company.com",
        None,
        "",
        "not-an-email",
        "replyguy@example.com",  # 'reply' alone must not trigger
    ],
)
def test_is_no_reply_sender_false_for_repliable_addresses(sender):
    assert is_no_reply_sender(sender) is False
