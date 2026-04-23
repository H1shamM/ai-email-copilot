"""Tests for app.ai.analyzer with mocked Claude client."""

from unittest.mock import MagicMock, patch

from app.ai import analyzer


def _make_response(text: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


@patch.object(analyzer, "_get_client")
def test_analyze_email_parses_valid_json(mock_get_client):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_response(
        '{"summary":"x","category":"Work","sentiment":"Casual",'
        '"action_required":"Reply","urgency_score":5,"key_dates":[],"key_people":[]}'
    )
    mock_get_client.return_value = mock_client

    result = analyzer.analyze_email({"sender": "a@a.com", "subject": "s", "body": "b"})
    assert result["category"] == "Work"
    assert result["urgency_score"] == 5


@patch.object(analyzer, "_get_client")
def test_analyze_email_strips_markdown_fences(mock_get_client):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_response(
        '```json\n{"summary":"x","category":"Personal","sentiment":"Casual",'
        '"action_required":"Read","urgency_score":2,"key_dates":[],"key_people":[]}\n```'
    )
    mock_get_client.return_value = mock_client

    result = analyzer.analyze_email({"sender": "a", "subject": "s", "snippet": "snip"})
    assert result["category"] == "Personal"


@patch.object(analyzer, "_get_client")
def test_analyze_email_returns_none_on_invalid_json(mock_get_client):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_response("not json at all")
    mock_get_client.return_value = mock_client

    assert analyzer.analyze_email({"sender": "a", "subject": "s", "body": ""}) is None


@patch.object(analyzer, "_get_client")
def test_analyze_email_returns_none_on_api_error(mock_get_client):
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = RuntimeError("API down")
    mock_get_client.return_value = mock_client

    assert analyzer.analyze_email({"sender": "a", "subject": "s", "body": ""}) is None


def test_analyze_email_falls_back_to_snippet_when_body_empty():
    """The prompt should use snippet if body is missing/empty."""
    captured = {}

    def fake_create(**kwargs):
        captured["prompt"] = kwargs["messages"][0]["content"]
        return _make_response(
            '{"summary":"x","category":"Work","sentiment":"Casual",'
            '"action_required":"Read","urgency_score":1,'
            '"key_dates":[],"key_people":[]}'
        )

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = fake_create
    with patch.object(analyzer, "_get_client", return_value=mock_client):
        analyzer.analyze_email({"sender": "a", "subject": "s", "snippet": "FALLBACK"})

    assert "FALLBACK" in captured["prompt"]
