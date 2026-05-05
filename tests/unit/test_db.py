"""Smoke tests for the database module."""

import pytest

from app.database import db


def test_init_db_creates_tables():
    conn = db.get_connection()
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    conn.close()
    expected = {
        "emails",
        "draft_replies",
        "calendar_events",
        "followups",
        "user_preferences",
        "telegram_users",
    }
    assert expected.issubset(tables)


def test_insert_email_returns_row_id():
    email = {
        "id": "msg_001",
        "thread_id": "thread_001",
        "sender": "alice@example.com",
        "subject": "Hello",
        "body": "Body text",
        "snippet": "Body...",
        "date": "2026-04-15",
    }
    row_id = db.insert_email(email)
    assert row_id is not None and row_id > 0


def test_insert_email_is_idempotent():
    email = {
        "id": "msg_dup",
        "thread_id": "t",
        "sender": "x@x.com",
        "subject": "s",
        "body": "b",
        "snippet": "s",
        "date": "2026-04-15",
    }
    db.insert_email(email)
    second = db.insert_email(email)
    # INSERT OR IGNORE returns 0 (or the existing rowid quirk) on dup; should not raise
    assert second is not None


def test_update_analysis_persists_fields():
    email = {
        "id": "msg_002",
        "thread_id": "t",
        "sender": "bob@example.com",
        "subject": "Meeting",
        "body": "",
        "snippet": "",
        "date": "2026-04-15",
    }
    db.insert_email(email)

    db.update_analysis(
        "msg_002",
        {
            "summary": "Meeting request",
            "category": "Work",
            "sentiment": "Casual",
            "action_required": "Reply",
            "urgency_score": 7,
        },
    )

    stored = db.get_email_by_gmail_id("msg_002")
    assert stored["ai_summary"] == "Meeting request"
    assert stored["category"] == "Work"
    assert stored["urgency_score"] == 7
    assert stored["processed_at"] is not None


def test_get_unprocessed_emails_excludes_analyzed():
    db.insert_email(
        {
            "id": "raw",
            "thread_id": "t",
            "sender": "a@a",
            "subject": "s",
            "body": "",
            "snippet": "",
            "date": "",
        }
    )
    db.insert_email(
        {
            "id": "done",
            "thread_id": "t",
            "sender": "a@a",
            "subject": "s",
            "body": "",
            "snippet": "",
            "date": "",
        }
    )
    db.update_analysis(
        "done",
        {
            "summary": "x",
            "category": "Work",
            "sentiment": "Casual",
            "action_required": "Read",
            "urgency_score": 1,
        },
    )

    unprocessed_ids = {e["gmail_message_id"] for e in db.get_unprocessed_emails()}
    assert "raw" in unprocessed_ids
    assert "done" not in unprocessed_ids


def _make_email(gmail_id: str = "msg_d") -> int:
    """Insert an email and return its sqlite rowid."""
    return db.insert_email(
        {
            "id": gmail_id,
            "thread_id": "t",
            "sender": "a@a",
            "subject": "s",
            "body": "",
            "snippet": "",
            "date": "",
        }
    )


def test_insert_draft_reply_round_trips():
    email_row = _make_email("d_one")
    draft_id = db.insert_draft_reply(email_row, "professional", "Dear Alice,\nThanks.")
    draft = db.get_draft_by_id(draft_id)
    assert draft["tone"] == "professional"
    assert draft["draft_text"] == "Dear Alice,\nThanks."
    assert draft["status"] == "pending"
    assert draft["was_sent"] == 0
    assert draft["sent_at"] is None


def test_get_drafts_for_email_returns_only_latest_per_tone():
    email_row = _make_email("d_two")
    db.insert_draft_reply(email_row, "brief", "v1")
    db.insert_draft_reply(email_row, "brief", "v2")  # regenerated
    db.insert_draft_reply(email_row, "friendly", "f1")

    drafts = db.get_drafts_for_email(email_row)
    assert len(drafts) == 2
    by_tone = {d["tone"]: d for d in drafts}
    assert by_tone["brief"]["draft_text"] == "v2"
    assert by_tone["friendly"]["draft_text"] == "f1"


def test_update_draft_status_to_sent_marks_sent_columns():
    email_row = _make_email("d_send")
    draft_id = db.insert_draft_reply(email_row, "brief", "Yep.")
    db.update_draft_status(draft_id, "sent", mark_sent=True)
    after = db.get_draft_by_id(draft_id)
    assert after["status"] == "sent"
    assert after["was_sent"] == 1
    assert after["sent_at"] is not None


def test_update_draft_status_with_text_overwrites_body():
    email_row = _make_email("d_edit")
    draft_id = db.insert_draft_reply(email_row, "friendly", "Hey :)")
    db.update_draft_status(draft_id, "edited", draft_text="Hey, see you Tuesday.")
    after = db.get_draft_by_id(draft_id)
    assert after["status"] == "edited"
    assert after["draft_text"] == "Hey, see you Tuesday."


def test_update_draft_status_rejects_unknown_status():
    email_row = _make_email("d_bad")
    draft_id = db.insert_draft_reply(email_row, "brief", "x")
    with pytest.raises(ValueError, match="Invalid draft status"):
        db.update_draft_status(draft_id, "approved-ish")


def test_get_draft_by_id_returns_none_for_missing():
    assert db.get_draft_by_id(99999) is None


def test_get_email_by_row_id_round_trips():
    rid = _make_email("d_lookup")
    found = db.get_email_by_row_id(rid)
    assert found["gmail_message_id"] == "d_lookup"
    assert db.get_email_by_row_id(99999) is None


def test_get_or_create_telegram_user_creates_on_first_call():
    user = db.get_or_create_telegram_user(123456789)
    assert user["chat_id"] == 123456789
    assert user["created_at"] is not None
    assert user["last_seen_at"] is not None


def test_get_or_create_telegram_user_bumps_last_seen():
    first = db.get_or_create_telegram_user(987654321)
    second = db.get_or_create_telegram_user(987654321)
    assert first["chat_id"] == second["chat_id"]
    # last_seen_at must have advanced (or at least not gone backwards)
    assert second["last_seen_at"] >= first["last_seen_at"]
    # created_at must NOT change on a re-call
    assert first["created_at"] == second["created_at"]
