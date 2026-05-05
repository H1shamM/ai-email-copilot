"""Unit tests for app/ai/prompts.py."""

import pytest

from app.ai.prompts import TONE_INSTRUCTIONS, TONES, build_reply_prompt


def test_three_tones_present():
    assert set(TONES) == {"professional", "friendly", "brief"}
    assert set(TONE_INSTRUCTIONS) == set(TONES)


def test_build_reply_prompt_includes_email_fields():
    email = {"sender": "alice@example.com", "subject": "Lunch?", "body": "Tuesday at 12?"}
    rendered = build_reply_prompt(email, "professional")
    assert "alice@example.com" in rendered
    assert "Lunch?" in rendered
    assert "Tuesday at 12?" in rendered
    assert "Formal" in rendered or "professional" in rendered


def test_build_reply_prompt_falls_back_to_snippet():
    """When body is empty, snippet should appear in the prompt."""
    email = {"sender": "x", "subject": "s", "body": "", "snippet": "Snippet text"}
    assert "Snippet text" in build_reply_prompt(email, "friendly")


def test_build_reply_prompt_handles_missing_fields():
    """No KeyError on a sparse email dict."""
    rendered = build_reply_prompt({}, "brief")
    assert "Unknown" in rendered
    assert "(no subject)" in rendered


def test_build_reply_prompt_rejects_unknown_tone():
    with pytest.raises(ValueError, match="Unknown tone"):
        build_reply_prompt({"sender": "a"}, "shouty")
