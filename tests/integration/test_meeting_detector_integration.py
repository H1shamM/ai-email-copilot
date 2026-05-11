"""Integration tests for Claude meeting detection.

Run with: pytest -m integration tests/integration/test_meeting_detector_integration.py

Costs money — every run hits the real Anthropic API. Keep test count low.
"""

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="Requires ANTHROPIC_API_KEY env var",
    ),
]


def test_detect_returns_structured_meeting_for_clear_request():
    """A meeting request email yields is_meeting=True with the documented shape."""
    from app.ai.meeting_detector import detect_meeting

    result = detect_meeting(
        {
            "sender": "alice@example.com",
            "subject": "Sync next Tuesday",
            "received_date": "Mon, 10 May 2026 09:00:00 +0000",
            "body": (
                "Hi! Can we meet next Tuesday at 3pm UK time for 30 minutes? "
                "We'll use Zoom. — Alice"
            ),
        }
    )

    assert result is not None, "Claude returned None — check API key / quota"
    assert result.get("is_meeting") is True
    assert isinstance(result.get("confidence"), (int, float))
    assert 0.0 <= result["confidence"] <= 1.0
    assert isinstance(result.get("participants"), list)
    # `proposed_datetime` may be None on ambiguous parsing, but for this input
    # we expect Claude to anchor on the received date and emit ISO 8601.
    if result.get("proposed_datetime"):
        assert "T" in result["proposed_datetime"]
