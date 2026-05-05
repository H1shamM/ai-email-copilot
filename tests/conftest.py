"""Shared pytest fixtures for the ai-email-copilot test suite."""

import importlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    """Use a fresh temporary SQLite database for every test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DATABASE_PATH", path)

    # Reload the db module so it picks up the new DATABASE_PATH at import time
    from app.database import db as db_module

    importlib.reload(db_module)
    db_module.init_db()

    yield path

    os.unlink(path)


@pytest.fixture
def sample_emails() -> list[dict]:
    """Canonical mock emails matching service.parse_email() output shape."""
    with open(FIXTURES_DIR / "sample_emails.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def authorized_update(monkeypatch):
    """A MagicMock Update from the authorized chat with reply_text as AsyncMock."""
    from app.database import db
    from app.telegram import handlers

    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    monkeypatch.setattr(db, "get_or_create_telegram_user", lambda _: {})
    update = MagicMock()
    update.effective_chat.id = 42
    update.effective_chat.send_chat_action = AsyncMock()
    update.effective_chat.send_message = AsyncMock()
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_anthropic_response():
    """Factory: build a stubbed Anthropic client whose messages.create returns `payload`.

    Usage:
        def test_something(monkeypatch, mock_anthropic_response):
            stub = mock_anthropic_response({"summary": "ok", "category": "Work"})
            monkeypatch.setattr("app.ai.analyzer._get_client", lambda: stub)
    """

    def _build(payload: dict):
        client = MagicMock()
        message = MagicMock()
        message.content = [MagicMock(text=json.dumps(payload))]
        client.messages.create.return_value = message
        return client

    return _build
