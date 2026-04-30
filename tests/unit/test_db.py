"""Smoke tests for the database module."""

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
