"""Tests for the @authorized_only decorator and _is_authorized helper."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.telegram import handlers
from app.telegram.handlers import _is_authorized, authorized_only


def test_is_authorized_true_on_match(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    assert _is_authorized(42) is True


def test_is_authorized_false_on_mismatch(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    assert _is_authorized(99) is False


def test_is_authorized_false_when_env_unset(monkeypatch):
    monkeypatch.delenv("TELEGRAM_AUTHORIZED_CHAT_ID", raising=False)
    assert _is_authorized(42) is False


def test_is_authorized_false_when_chat_id_none(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    assert _is_authorized(None) is False


def test_is_authorized_false_on_non_numeric_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "not-a-number")
    assert _is_authorized(42) is False


@pytest.mark.asyncio
async def test_authorized_only_forwards_when_authorized(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    inner = AsyncMock(return_value="called")
    wrapped = authorized_only(inner)
    update = MagicMock()
    update.effective_chat.id = 42
    result = await wrapped(update, None)
    assert result == "called"
    inner.assert_awaited_once()


@pytest.mark.asyncio
async def test_authorized_only_drops_when_unauthorized(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    inner = AsyncMock()
    wrapped = authorized_only(inner)
    update = MagicMock()
    update.effective_chat.id = 99
    result = await wrapped(update, None)
    assert result is None
    inner.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_replies_with_welcome(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    update = MagicMock()
    update.effective_chat.id = 42
    update.message.reply_text = AsyncMock()
    await handlers.start(update, None)
    update.message.reply_text.assert_awaited_once_with(handlers.WELCOME)


@pytest.mark.asyncio
async def test_help_replies_with_welcome(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    update = MagicMock()
    update.effective_chat.id = 42
    update.message.reply_text = AsyncMock()
    await handlers.help_command(update, None)
    update.message.reply_text.assert_awaited_once_with(handlers.WELCOME)
