"""Unit tests for app/ai/voice.py pure helpers (no live Gmail)."""

from datetime import datetime, timedelta

from app.ai import voice


def test_clean_sent_body_strips_quoted_reply_trailer():
    body = (
        "Sounds good, see you then.\n\n"
        "On Mon, 10 May 2026, Alice wrote:\n> the original\n> more quote"
    )
    assert voice.clean_sent_body(body) == "Sounds good, see you then."


def test_clean_sent_body_strips_quote_lines():
    body = "Yes please.\n> quoted line\nThanks"
    cleaned = voice.clean_sent_body(body)
    assert ">" not in cleaned
    assert "Yes please." in cleaned and "Thanks" in cleaned


def test_clean_sent_body_handles_none():
    assert voice.clean_sent_body(None) == ""


def test_select_samples_filters_by_length_and_caps_count():
    short = {"body": "too short"}
    good = {"body": "x" * 200}
    huge = {"body": "y" * 5000}
    emails = [short, good, huge] + [{"body": "z" * 150} for _ in range(10)]
    samples = voice.select_samples(emails)
    assert len(samples) <= voice.MAX_SAMPLES
    assert all(voice.MIN_SAMPLE_CHARS <= len(s) <= voice.MAX_SAMPLE_CHARS for s in samples)
    assert "too short" not in samples


def test_is_stale_logic():
    assert voice._is_stale(None) is True
    assert voice._is_stale("not-a-date") is True
    fresh = datetime.now().isoformat()
    assert voice._is_stale(fresh) is False
    old = (datetime.now() - timedelta(days=voice.REFRESH_DAYS + 1)).isoformat()
    assert voice._is_stale(old) is True
