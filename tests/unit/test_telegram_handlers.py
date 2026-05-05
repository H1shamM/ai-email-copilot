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


def _analyzed_email_row(row_id: int = 5) -> dict:
    return {
        "id": row_id,
        "gmail_message_id": "gmail-abc",
        "thread_id": "thread-xyz",
        "sender": "alice@example.com",
        "subject": "Lunch?",
        "body": "Tuesday at 12?",
        "snippet": "Tuesday",
        "processed_at": "2026-05-01T10:00:00",
        "ai_summary": "asks about lunch",
        "category": "Personal",
        "urgency_score": 4,
    }


@pytest.fixture
def reply_context():
    """Mock context with .args populated, mimicking python-telegram-bot."""
    ctx = MagicMock()
    ctx.args = []
    ctx.user_data = {}
    return ctx


@pytest.mark.asyncio
async def test_reply_command_rejects_missing_arg(monkeypatch, authorized_update, reply_context):
    await handlers.reply_command(authorized_update, reply_context)
    text = _all_reply_texts(authorized_update)
    assert "Usage: /reply" in text


@pytest.mark.asyncio
async def test_reply_command_rejects_unknown_email(monkeypatch, authorized_update, reply_context):
    monkeypatch.setattr(handlers.db, "get_email_by_row_id", lambda _: None)
    reply_context.args = ["999"]
    await handlers.reply_command(authorized_update, reply_context)
    assert "No email with id 999" in _all_reply_texts(authorized_update)


@pytest.mark.asyncio
async def test_reply_command_rejects_unanalyzed_email(
    monkeypatch, authorized_update, reply_context
):
    row = _analyzed_email_row()
    row["processed_at"] = None
    monkeypatch.setattr(handlers.db, "get_email_by_row_id", lambda _: row)
    reply_context.args = ["5"]
    await handlers.reply_command(authorized_update, reply_context)
    assert "hasn't been analyzed" in _all_reply_texts(authorized_update)


@pytest.mark.asyncio
async def test_reply_command_persists_drafts_and_renders(
    monkeypatch, authorized_update, reply_context
):
    row = _analyzed_email_row()
    monkeypatch.setattr(handlers.db, "get_email_by_row_id", lambda _: row)
    monkeypatch.setattr(
        handlers,
        "generate_replies",
        lambda email: {"professional": "Pro reply", "friendly": "Hey", "brief": "Yes"},
    )

    inserted: list[tuple] = []

    def fake_insert(email_id, tone, text):
        inserted.append((email_id, tone, text))
        return len(inserted)

    monkeypatch.setattr(handlers.db, "insert_draft_reply", fake_insert)
    monkeypatch.setattr(
        handlers.db,
        "get_draft_by_id",
        lambda did: {
            "id": did,
            "tone": inserted[did - 1][1],
            "draft_text": inserted[did - 1][2],
        },
    )
    reply_context.args = ["5"]
    await handlers.reply_command(authorized_update, reply_context)

    assert {t for _, t, _ in inserted} == {"professional", "friendly", "brief"}
    text = _all_reply_texts(authorized_update)
    assert "Drafting replies" in text
    assert "Professional" in text or "🎩" in text


@pytest.mark.asyncio
async def test_reply_command_handles_empty_generation(
    monkeypatch, authorized_update, reply_context
):
    monkeypatch.setattr(handlers.db, "get_email_by_row_id", lambda _: _analyzed_email_row())
    monkeypatch.setattr(handlers, "generate_replies", lambda _: {})
    reply_context.args = ["5"]
    await handlers.reply_command(authorized_update, reply_context)
    assert "Couldn't draft replies" in _all_reply_texts(authorized_update)


def _make_callback_update(data: str, chat_id: int = 42) -> MagicMock:
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.effective_chat.send_message = AsyncMock()
    update.callback_query.data = data
    update.callback_query.answer = AsyncMock()
    update.message = None
    return update


@pytest.mark.asyncio
async def test_cb_approve_sends_via_gmail_and_marks_sent(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    monkeypatch.setattr(
        handlers.db,
        "get_draft_by_id",
        lambda _: {
            "id": 7,
            "email_id": 5,
            "tone": "brief",
            "draft_text": "Yes.",
            "status": "pending",
        },
    )
    monkeypatch.setattr(handlers.db, "get_email_by_row_id", lambda _: _analyzed_email_row())

    sent_calls: list[tuple] = []

    def fake_send(thread_id, message_id, body):
        sent_calls.append((thread_id, message_id, body))
        return "new-msg-id"

    monkeypatch.setattr(handlers, "gmail_send_reply", fake_send)
    update_calls: list[tuple] = []
    monkeypatch.setattr(
        handlers.db,
        "update_draft_status",
        lambda did, status, **kw: update_calls.append((did, status, kw)),
    )

    update = _make_callback_update("r:approve:7")
    await handlers.cb_approve(update, reply_context)

    assert sent_calls == [("thread-xyz", "gmail-abc", "Yes.")]
    assert update_calls == [(7, "sent", {"mark_sent": True})]
    update.effective_chat.send_message.assert_awaited()
    msg = update.effective_chat.send_message.await_args_list[-1].args[0]
    assert "Reply sent" in msg


@pytest.mark.asyncio
async def test_cb_approve_handles_send_failure(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    monkeypatch.setattr(
        handlers.db,
        "get_draft_by_id",
        lambda _: {"id": 7, "email_id": 5, "tone": "brief", "draft_text": "x", "status": "pending"},
    )
    monkeypatch.setattr(handlers.db, "get_email_by_row_id", lambda _: _analyzed_email_row())

    def boom(*_):
        raise RuntimeError("token expired")

    monkeypatch.setattr(handlers, "gmail_send_reply", boom)
    update_calls: list[tuple] = []
    monkeypatch.setattr(
        handlers.db,
        "update_draft_status",
        lambda *a, **k: update_calls.append((a, k)),
    )

    update = _make_callback_update("r:approve:7")
    await handlers.cb_approve(update, reply_context)

    assert update_calls == []  # status NOT moved to sent
    msg = update.effective_chat.send_message.await_args_list[-1].args[0]
    assert "Send failed" in msg


@pytest.mark.asyncio
async def test_cb_approve_skips_sent_drafts(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    monkeypatch.setattr(
        handlers.db,
        "get_draft_by_id",
        lambda _: {"id": 7, "email_id": 5, "tone": "brief", "draft_text": "x", "status": "sent"},
    )
    send_called = False

    def fake_send(*_):
        nonlocal send_called
        send_called = True

    monkeypatch.setattr(handlers, "gmail_send_reply", fake_send)
    update = _make_callback_update("r:approve:7")
    await handlers.cb_approve(update, reply_context)
    assert send_called is False


@pytest.mark.asyncio
async def test_cb_skip_marks_all_pending_drafts_skipped(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    drafts = [
        {"id": 1, "status": "pending"},
        {"id": 2, "status": "pending"},
        {"id": 3, "status": "sent"},  # already sent — must NOT be touched
    ]
    monkeypatch.setattr(handlers.db, "get_drafts_for_email", lambda _: drafts)
    skipped: list[int] = []
    monkeypatch.setattr(
        handlers.db,
        "update_draft_status",
        lambda did, status, **_: skipped.append((did, status)),
    )

    update = _make_callback_update("r:skip:5")
    await handlers.cb_skip(update, reply_context)

    assert skipped == [(1, "skipped"), (2, "skipped")]
    msg = update.effective_chat.send_message.await_args_list[-1].args[0]
    assert "skipped" in msg


@pytest.mark.asyncio
async def test_cb_regenerate_replaces_only_chosen_tone(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    monkeypatch.setattr(
        handlers.db,
        "get_draft_by_id",
        lambda _: {
            "id": 9,
            "email_id": 5,
            "tone": "brief",
            "draft_text": "old",
            "status": "pending",
        },
    )
    monkeypatch.setattr(handlers.db, "get_email_by_row_id", lambda _: _analyzed_email_row())
    monkeypatch.setattr(handlers, "regenerate_one", lambda email, tone: "fresh take")

    updates: list[tuple] = []
    monkeypatch.setattr(
        handlers.db,
        "update_draft_status",
        lambda did, status, **kw: updates.append((did, status, kw)),
    )

    update = _make_callback_update("r:regen:9")
    await handlers.cb_regenerate(update, reply_context)

    assert updates == [(9, "pending", {"draft_text": "fresh take"})]
    msg = update.effective_chat.send_message.await_args_list[-1].args[0]
    assert "brief" in msg


@pytest.mark.asyncio
async def test_cb_regenerate_reports_failure(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    monkeypatch.setattr(
        handlers.db,
        "get_draft_by_id",
        lambda _: {
            "id": 9,
            "email_id": 5,
            "tone": "brief",
            "draft_text": "old",
            "status": "pending",
        },
    )
    monkeypatch.setattr(handlers.db, "get_email_by_row_id", lambda _: _analyzed_email_row())
    monkeypatch.setattr(handlers, "regenerate_one", lambda *_: None)
    update = _make_callback_update("r:regen:9")
    await handlers.cb_regenerate(update, reply_context)
    msg = update.effective_chat.send_message.await_args_list[-1].args[0]
    assert "Regenerate failed" in msg


@pytest.mark.asyncio
async def test_cb_edit_start_stashes_draft_id(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    monkeypatch.setattr(
        handlers.db,
        "get_draft_by_id",
        lambda _: {"id": 7, "tone": "friendly"},
    )
    update = _make_callback_update("r:edit:7")
    state = await handlers.cb_edit_start(update, reply_context)

    assert reply_context.user_data["editing_draft_id"] == 7
    assert state == handlers.WAITING_FOR_TEXT


@pytest.mark.asyncio
async def test_cb_edit_save_overwrites_then_sends(monkeypatch, authorized_update, reply_context):
    reply_context.user_data["editing_draft_id"] = 7
    authorized_update.message.text = "  My revised draft.  "
    authorized_update.effective_chat.send_message = AsyncMock()

    monkeypatch.setattr(
        handlers.db,
        "get_draft_by_id",
        lambda _: {
            "id": 7,
            "email_id": 5,
            "tone": "friendly",
            "draft_text": "My revised draft.",
            "status": "edited",
        },
    )
    monkeypatch.setattr(handlers.db, "get_email_by_row_id", lambda _: _analyzed_email_row())
    monkeypatch.setattr(handlers, "gmail_send_reply", lambda *_: "new-id")

    status_calls: list[tuple] = []
    monkeypatch.setattr(
        handlers.db,
        "update_draft_status",
        lambda did, status, **kw: status_calls.append((did, status, kw)),
    )

    state = await handlers.cb_edit_save(authorized_update, reply_context)

    assert state == -1
    # First call: 'edited' with the new text. Second call: 'sent' inside _send_draft.
    assert status_calls[0] == (7, "edited", {"draft_text": "My revised draft."})
    assert status_calls[1] == (7, "sent", {"mark_sent": True})


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
