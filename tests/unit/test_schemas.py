"""Tests for Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.models.schemas import AnalysisResult, DraftReply, Email


def test_email_minimal():
    e = Email(id="x")
    assert e.id == "x"
    assert e.snippet == ""


def test_analysis_result_required_fields():
    a = AnalysisResult(
        summary="s",
        category="Work",
        sentiment="Casual",
        action_required="Reply",
        urgency_score=5,
    )
    assert a.urgency_score == 5
    assert a.key_dates == []


def test_analysis_result_validates_types():
    with pytest.raises(ValidationError):
        AnalysisResult(
            summary="s",
            category="Work",
            sentiment="Casual",
            action_required="Reply",
            urgency_score="not-an-int",  # type: ignore
        )


def test_draft_reply_defaults():
    d = DraftReply(email_id="1", tone="friendly", draft_text="hi")
    assert d.was_sent is False
    assert d.sent_at is None
