"""Integration tests for fetching real emails from Gmail.

Run with: pytest -m integration tests/integration/test_email_fetching_integration.py
"""

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.path.exists("token.pickle"),
        reason="Requires authenticated token.pickle",
    ),
]


def test_fetch_recent_returns_parsed_emails():
    """Live Gmail call returns a list of parsed-email dicts with the expected keys."""
    from app.gmail.service import get_recent_emails

    emails = get_recent_emails(max_results=3, unread_only=False)
    assert isinstance(emails, list)
    if not emails:
        pytest.skip("Inbox empty — nothing to assert on")
    for email in emails:
        assert {"id", "thread_id", "sender", "subject", "date", "snippet", "body"} <= email.keys()
