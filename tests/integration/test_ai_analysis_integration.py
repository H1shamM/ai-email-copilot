"""Integration tests for Claude email analysis.

Run with: pytest -m integration tests/integration/test_ai_analysis_integration.py

These tests cost money — every run hits the real Anthropic API. Keep
the test count low and the inputs small.
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

VALID_CATEGORIES = {"Work", "Personal", "Newsletter", "Finance", "Travel", "Shopping", "Other"}
VALID_SENTIMENTS = {"Urgent", "Casual", "Formal"}
VALID_ACTIONS = {"Reply", "Schedule", "Read", "Archive", "Flag"}


def test_analyze_returns_well_shaped_dict(sample_emails):
    """A real Claude call returns the schema documented in analyzer.ANALYSIS_PROMPT."""
    from app.ai.analyzer import analyze_email

    result = analyze_email(sample_emails[0])

    assert result is not None, "Claude returned None — check API key / quota"
    assert isinstance(result.get("summary"), str) and result["summary"]
    assert result.get("category") in VALID_CATEGORIES
    assert result.get("sentiment") in VALID_SENTIMENTS
    assert result.get("action_required") in VALID_ACTIONS
    assert isinstance(result.get("urgency_score"), int)
    assert 1 <= result["urgency_score"] <= 10
