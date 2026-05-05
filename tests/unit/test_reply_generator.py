"""Unit tests for app/ai/reply_generator.py — Anthropic client is fully mocked."""

from unittest.mock import MagicMock

import pytest

from app.ai import reply_generator


def _stub_client(text: str) -> MagicMock:
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    client.messages.create.return_value = msg
    return client


def _stub_client_per_tone(by_tone: dict[str, str]) -> MagicMock:
    """Returns a client whose response varies based on the prompt's tone."""
    client = MagicMock()

    def fake_create(*, messages, **_):
        prompt = messages[0]["content"]
        for tone, text in by_tone.items():
            if f"Generate a {tone} email reply." in prompt:
                msg = MagicMock()
                msg.content = [MagicMock(text=text)]
                return msg
        msg = MagicMock()
        msg.content = [MagicMock(text="fallback")]
        return msg

    client.messages.create.side_effect = fake_create
    return client


@pytest.fixture
def patch_client(monkeypatch):
    def _apply(client):
        monkeypatch.setattr(reply_generator, "_get_client", lambda: client)

    return _apply


def test_generate_replies_returns_dict_keyed_by_tone(patch_client):
    patch_client(
        _stub_client_per_tone({"professional": "Pro reply", "friendly": "Hey!", "brief": "Yes."})
    )
    out = reply_generator.generate_replies({"sender": "a", "subject": "s", "body": "b"})
    assert out == {"professional": "Pro reply", "friendly": "Hey!", "brief": "Yes."}


def test_generate_replies_strips_markdown_fences(patch_client):
    patch_client(_stub_client("```\nFenced reply\n```"))
    out = reply_generator.generate_replies(
        {"sender": "a", "subject": "s", "body": "b"}, tones=("professional",)
    )
    assert out == {"professional": "Fenced reply"}


def test_generate_replies_skips_failed_tones(patch_client, monkeypatch):
    """If one tone raises, others still come through."""

    call_count = {"n": 0}

    def fake_get_client():
        client = MagicMock()

        def maybe_fail(**_):
            call_count["n"] += 1
            if call_count["n"] == 2:  # second tone fails
                raise RuntimeError("rate limited")
            msg = MagicMock()
            msg.content = [MagicMock(text="ok")]
            return msg

        client.messages.create.side_effect = maybe_fail
        return client

    monkeypatch.setattr(reply_generator, "_get_client", fake_get_client)
    out = reply_generator.generate_replies({"sender": "a"})
    assert "ok" in out.values()
    assert len(out) == 2


def test_regenerate_one_returns_text(patch_client):
    patch_client(_stub_client("Regenerated"))
    assert reply_generator.regenerate_one({"sender": "x"}, "brief") == "Regenerated"


def test_regenerate_one_returns_none_on_failure(patch_client):
    client = MagicMock()
    client.messages.create.side_effect = RuntimeError("nope")
    patch_client(client)
    assert reply_generator.regenerate_one({"sender": "x"}, "brief") is None


def test_lazy_client_is_singleton(monkeypatch):
    """_get_client builds the Anthropic client once and reuses it."""
    reply_generator._client = None
    construct = MagicMock(return_value="dummy")
    monkeypatch.setattr(reply_generator, "Anthropic", construct)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    a = reply_generator._get_client()
    b = reply_generator._get_client()
    assert a is b
    assert construct.call_count == 1
    reply_generator._client = None
