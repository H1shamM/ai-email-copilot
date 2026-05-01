"""End-to-end integration test: fetch -> analyze -> store -> retrieve.

Run with: pytest -m integration tests/integration/test_end_to_end.py

Requires both Gmail OAuth (token.pickle) and ANTHROPIC_API_KEY. Costs
money on every run because of the live Claude calls.
"""

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (os.path.exists("token.pickle") and os.getenv("ANTHROPIC_API_KEY")),
        reason="Requires token.pickle + ANTHROPIC_API_KEY",
    ),
]


def test_fetch_analyze_persist_pipeline(temp_db):
    """Pull a few real emails, run them through Claude, persist results, read back."""
    from app.ai.analyzer import analyze_email
    from app.database import db
    from app.gmail.service import get_recent_emails

    emails = get_recent_emails(max_results=2, unread_only=False)
    if not emails:
        pytest.skip("Inbox empty — nothing to analyze")

    for email in emails:
        db.insert_email(email)

    pending = db.get_unprocessed_emails()
    assert len(pending) == len(emails)

    analyzed_count = 0
    for email in pending:
        analysis = analyze_email(email)
        if analysis:
            db.update_analysis(email["gmail_message_id"], analysis)
            analyzed_count += 1

    assert analyzed_count >= 1, "Every Claude call failed — check API key / quota"

    rows = db.get_recent_emails(limit=10)
    persisted = [r for r in rows if r.get("processed_at")]
    assert len(persisted) == analyzed_count
    for row in persisted:
        assert row["ai_summary"]
        assert row["category"]
