"""Tests for /unread, /analyze, /inbox handlers in app/telegram/handlers.py."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.telegram import handlers


@pytest.fixture
def authorized_update(monkeypatch):
    """Authorized Update with an AsyncMock-backed reply_text and DB upsert stubbed."""
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    update = MagicMock()
    update.effective_chat.id = 42
    update.message.reply_text = AsyncMock()
    return update


def _all_reply_texts(update) -> str:
    """Concatenate every text passed to reply_text across all calls."""
    return "\n".join(call.args[0] for call in update.message.reply_text.await_args_list)


@pytest.mark.asyncio
async def test_unread_replies_with_numbered_list(monkeypatch, authorized_update):
    monkeypatch.setattr(
        handlers,
        "gmail_fetch_recent",
        lambda max_results, unread_only: [
            {"sender": "alice@example.com", "subject": "Hi", "snippet": "hello"},
            {"sender": "bob@example.com", "subject": "Lunch?", "snippet": "tomorrow?"},
        ],
    )
    await handlers.unread(authorized_update, None)
    text = _all_reply_texts(authorized_update)
    assert "*1\\.*" in text
    assert "*2\\.*" in text
    assert "alice@example\\.com" in text
    assert "bob@example\\.com" in text


@pytest.mark.asyncio
async def test_unread_replies_empty_message_when_no_unread(monkeypatch, authorized_update):
    monkeypatch.setattr(handlers, "gmail_fetch_recent", lambda max_results, unread_only: [])
    await handlers.unread(authorized_update, None)
    authorized_update.message.reply_text.assert_awaited_once_with("No unread emails.")


@pytest.mark.asyncio
async def test_unread_reports_gmail_error(monkeypatch, authorized_update):
    def raise_runtime(**_):
        raise RuntimeError("boom")

    monkeypatch.setattr(handlers, "gmail_fetch_recent", raise_runtime)
    await handlers.unread(authorized_update, None)
    text = _all_reply_texts(authorized_update)
    assert "Gmail error" in text
    assert "boom" in text


@pytest.mark.asyncio
async def test_analyze_runs_claude_and_persists(monkeypatch, authorized_update):
    pending = [
        {"gmail_message_id": "g1", "sender": "alice@example.com", "subject": "Hi", "body": "x"},
        {"gmail_message_id": "g2", "sender": "bob@example.com", "subject": "Re", "body": "y"},
    ]
    monkeypatch.setattr(handlers.db, "get_unprocessed_emails", lambda: pending)
    monkeypatch.setattr(
        handlers,
        "analyze_email",
        lambda email: {
            "summary": f"sum {email['gmail_message_id']}",
            "category": "Work",
            "urgency_score": 7,
        },
    )
    update_calls: list[tuple] = []
    monkeypatch.setattr(
        handlers.db,
        "update_analysis",
        lambda gid, analysis: update_calls.append((gid, analysis)),
    )

    await handlers.analyze(authorized_update, None)

    assert len(update_calls) == 2
    assert {c[0] for c in update_calls} == {"g1", "g2"}
    text = _all_reply_texts(authorized_update)
    assert "alice@example\\.com" in text
    assert "*Category:* Work" in text


@pytest.mark.asyncio
async def test_analyze_replies_empty_when_nothing_pending(monkeypatch, authorized_update):
    monkeypatch.setattr(handlers.db, "get_unprocessed_emails", list)
    await handlers.analyze(authorized_update, None)
    authorized_update.message.reply_text.assert_awaited_once_with("No emails to analyze.")


@pytest.mark.asyncio
async def test_analyze_adds_warning_block_on_claude_failure(monkeypatch, authorized_update):
    monkeypatch.setattr(
        handlers.db,
        "get_unprocessed_emails",
        lambda: [{"gmail_message_id": "g1", "sender": "alice@example.com"}],
    )
    monkeypatch.setattr(handlers, "analyze_email", lambda _: None)
    monkeypatch.setattr(handlers.db, "update_analysis", lambda *_: None)
    await handlers.analyze(authorized_update, None)
    text = _all_reply_texts(authorized_update)
    assert "⚠️" in text
    assert "analysis failed" in text


@pytest.mark.asyncio
async def test_inbox_lists_analyzed_rows(monkeypatch, authorized_update):
    rows = [
        {
            "sender": "alice@example.com",
            "subject": "Done",
            "ai_summary": "All set.",
            "urgency_score": 9,
            "processed_at": "2026-04-30T10:00:00",
        },
        {"sender": "skip@example.com", "subject": "ignore", "processed_at": None},
        {
            "sender": "bob@example.com",
            "subject": "Pending",
            "ai_summary": "Maybe.",
            "urgency_score": 3,
            "processed_at": "2026-04-30T11:00:00",
        },
    ]
    monkeypatch.setattr(handlers.db, "get_recent_emails", lambda limit: rows)
    await handlers.inbox(authorized_update, None)
    text = _all_reply_texts(authorized_update)
    assert "alice@example\\.com" in text
    assert "bob@example\\.com" in text
    assert "skip@example\\.com" not in text
    assert "🔴" in text
    assert "🟢" in text


@pytest.mark.asyncio
async def test_inbox_replies_empty_when_none_analyzed(monkeypatch, authorized_update):
    monkeypatch.setattr(handlers.db, "get_recent_emails", lambda limit: [])
    await handlers.inbox(authorized_update, None)
    authorized_update.message.reply_text.assert_awaited_once_with("No analyzed emails yet.")


@pytest.mark.asyncio
async def test_unread_drops_unauthorized(monkeypatch):
    """The @authorized_only guard still applies to the new handlers."""
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    fetch_called = False

    def fetch(**_):
        nonlocal fetch_called
        fetch_called = True
        return []

    monkeypatch.setattr(handlers, "gmail_fetch_recent", fetch)
    update = MagicMock()
    update.effective_chat.id = 99
    update.message.reply_text = AsyncMock()
    await handlers.unread(update, None)
    assert fetch_called is False
    update.message.reply_text.assert_not_awaited()
