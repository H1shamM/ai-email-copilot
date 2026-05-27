"""Tests for /unread, /analyze, /inbox handlers in app/telegram/handlers.py."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.telegram import handlers


@pytest.fixture
def authorized_update(monkeypatch):
    """Authorized Update with AsyncMock-backed reply_text + send_chat_action."""
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    update = MagicMock()
    update.effective_chat.id = 42
    update.effective_chat.send_chat_action = AsyncMock()
    update.effective_chat.send_message = AsyncMock()
    update.message.reply_text = AsyncMock()
    return update


def _all_reply_texts(update) -> str:
    """Concatenate every text passed to reply_text or chat.send_message."""
    pieces: list[str] = []
    for call in update.message.reply_text.await_args_list:
        if call.args:
            pieces.append(call.args[0])
    for call in update.effective_chat.send_message.await_args_list:
        if call.args:
            pieces.append(call.args[0])
        elif "text" in call.kwargs:
            pieces.append(call.kwargs["text"])
    return "\n".join(pieces)


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
async def test_unread_appends_clarifying_id_footer(monkeypatch, authorized_update):
    """The list numbers aren't /reply ids — a footer must say so to avoid the footgun."""
    monkeypatch.setattr(
        handlers,
        "gmail_fetch_recent",
        lambda max_results, unread_only: [{"sender": "a@b.com", "subject": "Hi", "snippet": "x"}],
    )
    await handlers.unread(authorized_update, None)
    text = _all_reply_texts(authorized_update)
    assert "not reply ids" in text
    assert "/inbox" in text


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
        {
            "id": 1,
            "gmail_message_id": "g1",
            "sender": "alice@example.com",
            "subject": "Hi",
            "body": "x",
        },
        {
            "id": 2,
            "gmail_message_id": "g2",
            "sender": "bob@example.com",
            "subject": "Re",
            "body": "y",
        },
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
        lambda: [{"id": 9, "gmail_message_id": "g1", "sender": "alice@example.com"}],
    )
    monkeypatch.setattr(handlers, "analyze_email", lambda _: None)
    monkeypatch.setattr(handlers.db, "update_analysis", lambda *_: None)
    await handlers.analyze(authorized_update, None)
    text = _all_reply_texts(authorized_update)
    assert "⚠️" in text
    assert "analysis failed" in text
    assert "\\#9" in text  # warning still surfaces the row id


@pytest.mark.asyncio
async def test_inbox_lists_analyzed_rows(monkeypatch, authorized_update):
    rows = [
        {
            "id": 4,
            "sender": "alice@example.com",
            "subject": "Done",
            "ai_summary": "All set.",
            "urgency_score": 9,
            "processed_at": "2026-04-30T10:00:00",
        },
        {"id": 5, "sender": "skip@example.com", "subject": "ignore", "processed_at": None},
        {
            "id": 6,
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
    assert "\\#4" in text  # row ids visible so /reply target is obvious
    assert "\\#6" in text
    assert "🔴" in text
    assert "🟢" in text
    assert "/reply <id>" in text  # helper tip footer


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
async def test_reply_command_notes_ignored_extra_args(
    monkeypatch, authorized_update, reply_context
):
    """`/reply 5 banana` must run for id 5 but tell the user 'banana' was ignored."""
    flow_calls: list = []

    async def fake_flow(update, email_id):
        flow_calls.append(email_id)

    monkeypatch.setattr(handlers, "_run_reply_flow", fake_flow)
    reply_context.args = ["5", "banana"]
    await handlers.reply_command(authorized_update, reply_context)

    assert flow_calls == [5]  # still ran for the valid id
    text = _all_reply_texts(authorized_update)
    assert "Ignoring extra argument" in text
    assert "banana" in text


@pytest.mark.asyncio
async def test_analyze_notes_ignored_args(monkeypatch, authorized_update, reply_context):
    """`/analyze 999` must say the arg is ignored and still run normally."""
    monkeypatch.setattr(handlers.db, "get_unprocessed_emails", list)
    reply_context.args = ["999"]
    await handlers.analyze(authorized_update, reply_context)

    text = _all_reply_texts(authorized_update)
    assert "ignoring" in text.lower()
    assert "999" in text
    assert "No emails to analyze." in text


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
    assert "Drafting" in text
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


@pytest.mark.asyncio
async def test_reply_drafting_message_has_realistic_eta(monkeypatch, authorized_update):
    """The progress message must not under-promise the ~1 min generation time."""
    monkeypatch.setattr(handlers.db, "get_email_by_row_id", lambda _: _analyzed_email_row())
    monkeypatch.setattr(handlers, "generate_replies", lambda _: {"brief": "Yes"})
    monkeypatch.setattr(handlers.db, "insert_draft_reply", lambda *_: 1)
    monkeypatch.setattr(
        handlers.db,
        "get_draft_by_id",
        lambda did: {"id": did, "tone": "brief", "draft_text": "Yes"},
    )
    await handlers._run_reply_flow(authorized_update, 5)
    text = _all_reply_texts(authorized_update)
    assert "Drafting" in text
    assert "~10s" not in text
    assert "minute" in text


@pytest.mark.asyncio
async def test_reply_command_skips_no_reply_sender(monkeypatch, authorized_update, reply_context):
    """A no-reply sender must be refused before any draft is generated."""
    row = _analyzed_email_row()
    row["sender"] = "LinkedIn <messages-noreply@linkedin.com>"
    monkeypatch.setattr(handlers.db, "get_email_by_row_id", lambda _: row)

    gen_called = False

    def fake_generate(_):
        nonlocal gen_called
        gen_called = True
        return {"brief": "Yes"}

    monkeypatch.setattr(handlers, "generate_replies", fake_generate)
    reply_context.args = ["5"]
    await handlers.reply_command(authorized_update, reply_context)

    assert gen_called is False  # never reached draft generation
    text = _all_reply_texts(authorized_update)
    assert "no-reply address" in text
    assert "Drafting" not in text


@pytest.mark.asyncio
async def test_cb_approve_blocks_no_reply_send(monkeypatch, reply_context):
    """Defense-in-depth: approving a draft for a no-reply email must not send."""
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    monkeypatch.setattr(
        handlers.db,
        "get_draft_by_id",
        lambda _: {
            "id": 7,
            "email_id": 5,
            "tone": "brief",
            "draft_text": "Yes",
            "status": "pending",
        },
    )
    row = _analyzed_email_row()
    row["sender"] = "notifications-noreply@linkedin.com"
    monkeypatch.setattr(handlers.db, "get_email_by_row_id", lambda _: row)

    send_called = False

    def fake_send(*_):
        nonlocal send_called
        send_called = True
        return "id"

    monkeypatch.setattr(handlers, "gmail_send_reply", fake_send)
    status_calls: list = []
    monkeypatch.setattr(
        handlers.db, "update_draft_status", lambda *a, **k: status_calls.append((a, k))
    )

    update = _make_callback_update("r:approve:7")
    await handlers.cb_approve(update, reply_context)

    assert send_called is False
    assert status_calls == []  # draft NOT marked sent
    assert "no-reply address" in update.effective_chat.send_message.await_args_list[-1].args[0]


def _make_callback_update(data: str, chat_id: int = 42) -> MagicMock:
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.effective_chat.send_message = AsyncMock()
    update.effective_chat.send_chat_action = AsyncMock()
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
async def test_unread_sends_typing_indicator(monkeypatch, authorized_update):
    monkeypatch.setattr(handlers, "gmail_fetch_recent", lambda max_results, unread_only: [])
    await handlers.unread(authorized_update, None)
    authorized_update.effective_chat.send_chat_action.assert_awaited()


@pytest.mark.asyncio
async def test_analyze_sends_progress_placeholder_when_pending(monkeypatch, authorized_update):
    monkeypatch.setattr(
        handlers.db,
        "get_unprocessed_emails",
        lambda: [
            {"id": 1, "gmail_message_id": "g1", "sender": "a@a", "subject": "s", "body": "x"},
            {"id": 2, "gmail_message_id": "g2", "sender": "b@b", "subject": "s", "body": "y"},
        ],
    )
    monkeypatch.setattr(
        handlers,
        "analyze_email",
        lambda email: {
            "summary": "ok",
            "category": "Work",
            "sentiment": "Casual",
            "action_required": "Reply",
            "urgency_score": 3,
        },
    )
    monkeypatch.setattr(handlers.db, "update_analysis", lambda *_: None)

    await handlers.analyze(authorized_update, None)

    text = _all_reply_texts(authorized_update)
    assert "Analyzing 2 emails" in text
    authorized_update.effective_chat.send_chat_action.assert_awaited()


@pytest.mark.asyncio
async def test_analyze_skips_progress_placeholder_when_empty(monkeypatch, authorized_update):
    monkeypatch.setattr(handlers.db, "get_unprocessed_emails", list)
    await handlers.analyze(authorized_update, None)
    authorized_update.message.reply_text.assert_awaited_once_with("No emails to analyze.")


@pytest.mark.asyncio
async def test_typing_failure_does_not_break_command(monkeypatch, authorized_update):
    """If send_chat_action raises, the command must still complete."""
    authorized_update.effective_chat.send_chat_action.side_effect = RuntimeError("api down")
    monkeypatch.setattr(handlers, "gmail_fetch_recent", lambda max_results, unread_only: [])
    await handlers.unread(authorized_update, None)
    authorized_update.message.reply_text.assert_awaited_once_with("No unread emails.")


@pytest.mark.asyncio
async def test_pause_command_calls_push_pause_and_replies(monkeypatch, authorized_update):
    pause_calls = {"n": 0}

    def fake_pause():
        pause_calls["n"] += 1
        return True

    monkeypatch.setattr(handlers.telegram_push, "pause", fake_pause)
    await handlers.pause_command(authorized_update, None)
    assert pause_calls["n"] == 1
    text = _all_reply_texts(authorized_update)
    assert "paused" in text.lower()


@pytest.mark.asyncio
async def test_pause_command_idempotent_when_already_paused(monkeypatch, authorized_update):
    monkeypatch.setattr(handlers.telegram_push, "pause", lambda: False)
    await handlers.pause_command(authorized_update, None)
    text = _all_reply_texts(authorized_update)
    assert "paused" in text.lower()


@pytest.mark.asyncio
async def test_resume_command_calls_push_resume_and_replies(monkeypatch, authorized_update):
    resume_calls = {"n": 0}

    def fake_resume():
        resume_calls["n"] += 1
        return True

    monkeypatch.setattr(handlers.telegram_push, "resume", fake_resume)
    await handlers.resume_command(authorized_update, None)
    assert resume_calls["n"] == 1
    text = _all_reply_texts(authorized_update)
    assert "resumed" in text.lower()


@pytest.mark.asyncio
async def test_cb_notify_done_marks_archived_and_edits_message(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})

    done_calls: list[int] = []
    monkeypatch.setattr(handlers.db, "mark_email_done", lambda rid: done_calls.append(rid))

    update = _make_callback_update("n:done:5")
    update.callback_query.edit_message_text = AsyncMock()
    await handlers.cb_notify_done(update, reply_context)

    assert done_calls == [5]
    update.callback_query.edit_message_text.assert_awaited_once_with("✅ Done.")


@pytest.mark.asyncio
async def test_cb_notify_done_falls_back_when_edit_fails(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    monkeypatch.setattr(handlers.db, "mark_email_done", lambda _: None)

    update = _make_callback_update("n:done:5")
    update.callback_query.edit_message_text = AsyncMock(side_effect=RuntimeError("can't edit"))
    await handlers.cb_notify_done(update, reply_context)

    update.effective_chat.send_message.assert_awaited()
    msg = update.effective_chat.send_message.await_args_list[-1].args[0]
    assert "Done" in msg


@pytest.mark.asyncio
async def test_cb_notify_reply_runs_reply_flow_without_mutating_update(monkeypatch, reply_context):
    """Critical: must not assign update.message — PTB freezes Update objects."""
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})

    captured: dict = {}

    async def fake_flow(update, email_id):
        captured["email_id"] = email_id
        captured["chat_id"] = update.effective_chat.id

    monkeypatch.setattr(handlers, "_run_reply_flow", fake_flow)

    update = _make_callback_update("n:reply:7")
    original_message = update.message
    await handlers.cb_notify_reply(update, reply_context)

    assert captured == {"email_id": 7, "chat_id": 42}
    # Regression guard: cb must not have mutated update.message.
    assert update.message is original_message


@pytest.mark.asyncio
async def test_run_reply_flow_falls_back_to_plain_text_on_markdown_error(
    monkeypatch, authorized_update
):
    """If MARKDOWN_V2 send raises, the user must still get the drafts as plain text."""
    monkeypatch.setattr(
        handlers.db,
        "get_email_by_row_id",
        lambda _: _analyzed_email_row(),
    )
    monkeypatch.setattr(
        handlers,
        "generate_replies",
        lambda _: {"professional": "P", "friendly": "F", "brief": "B"},
    )
    monkeypatch.setattr(handlers.db, "insert_draft_reply", lambda *_: 1)
    monkeypatch.setattr(
        handlers.db,
        "get_draft_by_id",
        lambda did: {"id": did, "tone": "professional", "draft_text": "P"},
    )

    calls = []

    async def fake_send(text, **kwargs):
        calls.append(kwargs.get("parse_mode"))
        if kwargs.get("parse_mode") is not None:
            raise RuntimeError("Bad Request: can't parse entities")

    authorized_update.effective_chat.send_message = AsyncMock(side_effect=fake_send)

    await handlers._run_reply_flow(authorized_update, 5)

    # Must have tried MarkdownV2 first, then retried without parse_mode.
    assert any(p is not None for p in calls)
    assert any(p is None for p in calls)


@pytest.mark.asyncio
async def test_cb_notify_done_ignores_malformed_callback(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    done_calls: list[int] = []
    monkeypatch.setattr(handlers.db, "mark_email_done", lambda rid: done_calls.append(rid))

    update = _make_callback_update("n:wrong:5")  # action != 'done'
    await handlers.cb_notify_done(update, reply_context)
    assert done_calls == []


@pytest.mark.asyncio
async def test_set_bot_commands_registers_all_commands():
    """All 9 user-facing commands must be sent to Telegram's set_my_commands."""
    application = MagicMock()
    application.bot.set_my_commands = AsyncMock()

    await handlers.set_bot_commands(application)

    application.bot.set_my_commands.assert_awaited_once()
    sent = application.bot.set_my_commands.await_args.args[0]
    names = {c.command for c in sent}
    assert names == {
        "start",
        "help",
        "unread",
        "analyze",
        "inbox",
        "reply",
        "schedule",
        "agent",
        "pause",
        "resume",
    }
    # Every command needs a non-empty description so the popup row isn't blank.
    assert all(c.description for c in sent)


@pytest.mark.asyncio
async def test_set_bot_commands_swallows_failure(caplog):
    """If Telegram is unreachable, startup must continue without crashing."""
    application = MagicMock()
    application.bot.set_my_commands = AsyncMock(side_effect=RuntimeError("network"))

    with caplog.at_level("WARNING", logger="app.telegram.handlers"):
        await handlers.set_bot_commands(application)  # must NOT raise

    assert any("set_my_commands failed" in r.getMessage() for r in caplog.records)


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


def _detected_event(**overrides) -> dict:
    """A detected calendar_events row with a concrete date+time."""
    base = {
        "id": 3,
        "title": "Sync with Alice",
        "event_date": "2026-05-19",
        "event_time": "15:00:00",
        "duration_minutes": 60,
        "participants": "alice@x.com",
        "location": "Zoom",
        "status": "detected",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_schedule_command_lists_dated_detected_and_hides_undated(
    monkeypatch, authorized_update
):
    events = [
        _detected_event(id=1, title="Has time"),
        _detected_event(id=2, title="No time", event_time=None),
        _detected_event(id=3, title="No date", event_date=None),
    ]
    monkeypatch.setattr(handlers.db, "get_calendar_events_by_status", lambda _: events)
    await handlers.schedule_command(authorized_update, None)

    texts = _all_reply_texts(authorized_update)
    assert "Has time" in texts
    assert "No time" not in texts
    assert "No date" not in texts
    # Exactly one message per schedulable event.
    assert authorized_update.effective_chat.send_message.await_count == 1


@pytest.mark.asyncio
async def test_schedule_command_empty(monkeypatch, authorized_update):
    monkeypatch.setattr(handlers.db, "get_calendar_events_by_status", lambda _: [])
    await handlers.schedule_command(authorized_update, None)
    assert "No meetings to schedule." in _all_reply_texts(authorized_update)


@pytest.mark.asyncio
async def test_cb_schedule_create_free_window_creates(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    monkeypatch.setattr(handlers.db, "get_calendar_event_by_id", lambda _: _detected_event())
    monkeypatch.setattr(handlers.scheduler, "has_conflict", lambda _: False)
    monkeypatch.setattr(handlers.scheduler, "create_event", lambda _: "goog_evt_99")
    status_calls: list[tuple] = []
    monkeypatch.setattr(
        handlers.db,
        "update_calendar_event_status",
        lambda eid, status, **kw: status_calls.append((eid, status, kw)),
    )

    update = _make_callback_update("s:create:3")
    await handlers.cb_schedule_create(update, reply_context)

    assert status_calls == [(3, "created", {"google_event_id": "goog_evt_99"})]
    assert "Event created" in update.effective_chat.send_message.await_args_list[-1].args[0]


@pytest.mark.asyncio
async def test_cb_schedule_create_conflict_blocks(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    monkeypatch.setattr(handlers.db, "get_calendar_event_by_id", lambda _: _detected_event())
    monkeypatch.setattr(handlers.scheduler, "has_conflict", lambda _: True)

    create_called = False

    def _boom(_):
        nonlocal create_called
        create_called = True
        return "x"

    monkeypatch.setattr(handlers.scheduler, "create_event", _boom)
    status_calls: list[tuple] = []
    monkeypatch.setattr(
        handlers.db,
        "update_calendar_event_status",
        lambda *a, **k: status_calls.append((a, k)),
    )

    update = _make_callback_update("s:create:3")
    await handlers.cb_schedule_create(update, reply_context)

    assert create_called is False
    assert status_calls == []  # status stays 'detected'
    assert "Conflicts" in update.effective_chat.send_message.await_args_list[-1].args[0]


@pytest.mark.asyncio
async def test_cb_schedule_create_api_failure_marks_failed(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    monkeypatch.setattr(handlers.db, "get_calendar_event_by_id", lambda _: _detected_event())
    monkeypatch.setattr(handlers.scheduler, "has_conflict", lambda _: False)

    def boom(_):
        raise RuntimeError("calendar 500")

    monkeypatch.setattr(handlers.scheduler, "create_event", boom)
    status_calls: list[tuple] = []
    monkeypatch.setattr(
        handlers.db,
        "update_calendar_event_status",
        lambda eid, status, **kw: status_calls.append((eid, status, kw)),
    )

    update = _make_callback_update("s:create:3")
    await handlers.cb_schedule_create(update, reply_context)

    assert status_calls == [(3, "failed", {})]
    assert "Create failed" in update.effective_chat.send_message.await_args_list[-1].args[0]


@pytest.mark.asyncio
async def test_cb_schedule_create_idempotent_when_already_created(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    monkeypatch.setattr(
        handlers.db, "get_calendar_event_by_id", lambda _: _detected_event(status="created")
    )
    create_called = False

    def _boom(_):
        nonlocal create_called
        create_called = True
        return "x"

    monkeypatch.setattr(handlers.scheduler, "create_event", _boom)
    update = _make_callback_update("s:create:3")
    await handlers.cb_schedule_create(update, reply_context)

    assert create_called is False
    assert "already created" in update.effective_chat.send_message.await_args_list[-1].args[0]


@pytest.mark.asyncio
async def test_cb_schedule_skip_marks_skipped(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    monkeypatch.setattr(handlers.db, "get_calendar_event_by_id", lambda _: _detected_event())
    status_calls: list[tuple] = []
    monkeypatch.setattr(
        handlers.db,
        "update_calendar_event_status",
        lambda eid, status, **kw: status_calls.append((eid, status, kw)),
    )

    update = _make_callback_update("s:skip:3")
    await handlers.cb_schedule_skip(update, reply_context)

    assert status_calls == [(3, "skipped", {})]
    assert "Skipped" in update.effective_chat.send_message.await_args_list[-1].args[0]


@pytest.mark.asyncio
async def test_agent_command_empty_instruction_shows_usage(authorized_update, reply_context):
    reply_context.args = []
    await handlers.agent_command(authorized_update, reply_context)
    assert "Usage: /agent" in _all_reply_texts(authorized_update)


@pytest.mark.asyncio
async def test_agent_command_text_only_no_pending(monkeypatch, authorized_update, reply_context):
    monkeypatch.setattr(handlers.agent, "run_agent", lambda instr: ("Here is your summary.", []))
    reply_context.args = ["summarize", "my", "unread"]
    await handlers.agent_command(authorized_update, reply_context)

    assert "Here is your summary." in _all_reply_texts(authorized_update)
    assert "agent_pending" not in reply_context.user_data


@pytest.mark.asyncio
async def test_agent_command_deletes_status_message(monkeypatch, authorized_update, reply_context):
    status = MagicMock()
    status.delete = AsyncMock()
    authorized_update.effective_chat.send_message = AsyncMock(return_value=status)
    monkeypatch.setattr(handlers.agent, "run_agent", lambda instr: ("Summary.", []))
    reply_context.args = ["summarize"]

    await handlers.agent_command(authorized_update, reply_context)

    # The transient "🤖 Working on it…" status is removed, not left orphaned.
    status.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_agent_command_with_pending_shows_keyboard_and_stores(
    monkeypatch, authorized_update, reply_context
):
    pending = [{"name": "send_reply", "input": {"email_id": 5, "body": "Yes"}}]
    monkeypatch.setattr(handlers.agent, "run_agent", lambda instr: ("Proposed.", pending))
    monkeypatch.setattr(handlers.agent, "describe_action", lambda a: "Send reply to email 5")
    reply_context.args = ["reply", "to", "5"]
    await handlers.agent_command(authorized_update, reply_context)

    assert reply_context.user_data["agent_pending"] == pending
    calls = authorized_update.effective_chat.send_message.await_args_list
    assert any("reply_markup" in c.kwargs for c in calls)
    assert "Proposed actions" in _all_reply_texts(authorized_update)


@pytest.mark.asyncio
async def test_agent_command_handles_run_failure(monkeypatch, authorized_update, reply_context):
    def boom(_):
        raise RuntimeError("api down")

    monkeypatch.setattr(handlers.agent, "run_agent", boom)
    reply_context.args = ["do", "stuff"]
    await handlers.agent_command(authorized_update, reply_context)
    assert "Agent failed" in _all_reply_texts(authorized_update)


@pytest.mark.asyncio
async def test_cb_agent_approve_executes_queued_actions(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    executed: list = []
    monkeypatch.setattr(handlers.agent, "execute_action", lambda a: executed.append(a) or "did it")
    reply_context.user_data = {
        "agent_pending": [{"name": "send_reply", "input": {"email_id": 5, "body": "Yes"}}]
    }
    update = _make_callback_update("a:approve")
    await handlers.cb_agent_approve(update, reply_context)

    assert executed == [{"name": "send_reply", "input": {"email_id": 5, "body": "Yes"}}]
    assert "did it" in update.effective_chat.send_message.await_args_list[-1].args[0]
    assert "agent_pending" not in reply_context.user_data


@pytest.mark.asyncio
async def test_cb_agent_approve_no_pending(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    reply_context.user_data = {}
    update = _make_callback_update("a:approve")
    await handlers.cb_agent_approve(update, reply_context)
    assert "No pending actions" in update.effective_chat.send_message.await_args_list[-1].args[0]


@pytest.mark.asyncio
async def test_cb_agent_approve_reports_action_failure(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})

    def boom(_):
        raise RuntimeError("send fail")

    monkeypatch.setattr(handlers.agent, "execute_action", boom)
    reply_context.user_data = {"agent_pending": [{"name": "send_reply", "input": {}}]}
    update = _make_callback_update("a:approve")
    await handlers.cb_agent_approve(update, reply_context)
    assert "failed" in update.effective_chat.send_message.await_args_list[-1].args[0]


@pytest.mark.asyncio
async def test_cb_agent_cancel_discards(monkeypatch, reply_context):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(handlers.db, "get_or_create_telegram_user", lambda _: {})
    reply_context.user_data = {"agent_pending": [{"name": "send_reply", "input": {}}]}
    update = _make_callback_update("a:cancel")
    await handlers.cb_agent_cancel(update, reply_context)
    assert "agent_pending" not in reply_context.user_data
    assert "Cancelled" in update.effective_chat.send_message.await_args_list[-1].args[0]


@pytest.mark.asyncio
async def test_unknown_command_replies_hint(authorized_update):
    await handlers.unknown_command(authorized_update, None)
    text = _all_reply_texts(authorized_update)
    assert "Unknown command" in text
    assert "/help" in text


@pytest.mark.asyncio
async def test_fallback_text_replies_hint(authorized_update):
    await handlers.fallback_text(authorized_update, None)
    text = _all_reply_texts(authorized_update)
    assert "/help" in text


@pytest.mark.asyncio
async def test_unknown_command_drops_unauthorized(monkeypatch):
    """The @authorized_only guard must still silently drop foreign chats."""
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    update = MagicMock()
    update.effective_chat.id = 99
    update.message.reply_text = AsyncMock()
    await handlers.unknown_command(update, None)
    update.message.reply_text.assert_not_awaited()


def test_register_adds_exactly_two_fallback_message_handlers():
    """Fallbacks must be registered (and only the two), so plain text/unknown
    commands get a reply without shadowing the edit ConversationHandler."""
    from telegram.ext import MessageHandler

    app = MagicMock()
    handlers.register(app)
    added = [c.args[0] for c in app.add_handler.call_args_list]
    msg_handlers = [h for h in added if isinstance(h, MessageHandler)]
    assert len(msg_handlers) == 2
