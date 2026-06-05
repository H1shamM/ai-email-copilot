"""Smoke tests for the database module."""

import importlib
import os
import sqlite3
import tempfile

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


def test_get_recent_emails_orders_newest_first_deterministically():
    """Equal created_at (batch inserts) must break ties on id DESC, not arbitrarily."""
    for i in range(1, 4):
        db.insert_email(
            {
                "id": f"m{i}",
                "thread_id": "t",
                "sender": "a@b.com",
                "subject": f"s{i}",
                "body": "b",
                "snippet": "",
                "date": "2026-04-15",
            }
        )
    rows = db.get_recent_emails(limit=10)
    ids = [r["id"] for r in rows]
    assert ids == [3, 2, 1]


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


def test_count_analyzed_emails_counts_only_processed():
    for gid in ("c_raw", "c_done1", "c_done2"):
        db.insert_email(
            {
                "id": gid,
                "thread_id": "t",
                "sender": "a@a",
                "subject": "s",
                "snippet": "",
                "date": "",
            }
        )
    for gid in ("c_done1", "c_done2"):
        db.update_analysis(gid, {"summary": "x", "category": "Work", "urgency_score": 1})

    assert db.count_analyzed_emails() == 2


def test_mark_email_done_removes_from_recent_and_count():
    rid = db.insert_email(
        {
            "id": "arch1",
            "thread_id": "t",
            "sender": "a@a",
            "subject": "s",
            "snippet": "",
            "date": "",
        }
    )
    db.update_analysis("arch1", {"summary": "x", "category": "Work", "urgency_score": 2})
    assert any(r["id"] == rid for r in db.get_recent_emails())
    before = db.count_analyzed_emails()

    db.mark_email_done(rid)

    assert all(r["id"] != rid for r in db.get_recent_emails())  # archived → gone from inbox
    assert db.count_analyzed_emails() == before - 1


def test_preference_round_trips_and_upserts():
    assert db.get_preference("voice_samples") is None
    db.set_preference("voice_samples", "v1")
    assert db.get_preference("voice_samples") == "v1"
    db.set_preference("voice_samples", "v2")  # upsert, not duplicate
    assert db.get_preference("voice_samples") == "v2"


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


def test_init_db_migrates_pre_story_c_schema(monkeypatch):
    """A DB created before Story C/D (no draft_replies.status, no emails.notified_at)
    must migrate cleanly when init_db runs again — no 'no such column' error from
    indexes referencing the new columns.
    """
    fd, legacy_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        legacy = sqlite3.connect(legacy_path)
        legacy.executescript("""
            CREATE TABLE emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gmail_message_id TEXT UNIQUE NOT NULL,
                thread_id TEXT,
                sender TEXT NOT NULL,
                subject TEXT,
                body TEXT,
                snippet TEXT,
                received_date TEXT,
                ai_summary TEXT,
                category TEXT,
                sentiment TEXT,
                action_required TEXT,
                urgency_score INTEGER,
                is_read INTEGER DEFAULT 0,
                is_archived INTEGER DEFAULT 0,
                is_starred INTEGER DEFAULT 0,
                processed_at TEXT,
                created_at TEXT
            );
            CREATE TABLE draft_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER NOT NULL,
                tone TEXT NOT NULL,
                draft_text TEXT NOT NULL,
                was_sent INTEGER DEFAULT 0,
                sent_at TEXT,
                created_at TEXT
            );
            """)
        legacy.commit()
        legacy.close()

        monkeypatch.setenv("DATABASE_PATH", legacy_path)
        reloaded = importlib.reload(db)
        reloaded.init_db()  # must not raise

        check = reloaded.get_connection()
        try:
            cols_emails = {r["name"] for r in check.execute("PRAGMA table_info(emails)")}
            cols_drafts = {r["name"] for r in check.execute("PRAGMA table_info(draft_replies)")}
        finally:
            check.close()
        assert "notified_at" in cols_emails
        assert "status" in cols_drafts
    finally:
        os.unlink(legacy_path)


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


def test_insert_calendar_event_round_trips():
    email_row = _make_email("cal_one")
    event_row = db.insert_calendar_event(
        email_row,
        "Sync with Alice",
        event_date="2026-05-12",
        event_time="14:00",
        duration_minutes=30,
        participants="alice@example.com",
        location="Zoom",
    )
    events = db.get_calendar_event_by_email(email_row)
    assert len(events) == 1
    e = events[0]
    assert e["id"] == event_row
    assert e["title"] == "Sync with Alice"
    assert e["event_date"] == "2026-05-12"
    assert e["duration_minutes"] == 30
    assert e["participants"] == "alice@example.com"
    assert e["location"] == "Zoom"
    assert e["status"] == "detected"
    assert e["google_event_id"] is None


def test_get_calendar_event_by_email_returns_newest_first():
    email_row = _make_email("cal_multi")
    db.insert_calendar_event(email_row, "First detection")
    db.insert_calendar_event(email_row, "Second detection")
    events = db.get_calendar_event_by_email(email_row)
    assert [e["title"] for e in events] == ["Second detection", "First detection"]


def test_get_calendar_event_by_email_empty_when_none_exist():
    email_row = _make_email("cal_none")
    assert db.get_calendar_event_by_email(email_row) == []


def test_update_calendar_event_status_stamps_google_event_id():
    email_row = _make_email("cal_create")
    event_row = db.insert_calendar_event(email_row, "Quick chat")
    db.update_calendar_event_status(event_row, "created", google_event_id="goog_evt_42")
    after = db.get_calendar_event_by_email(email_row)[0]
    assert after["status"] == "created"
    assert after["google_event_id"] == "goog_evt_42"


def test_update_calendar_event_status_without_google_id_leaves_it():
    email_row = _make_email("cal_skip")
    event_row = db.insert_calendar_event(email_row, "Maybe meeting", google_event_id="prev")
    db.update_calendar_event_status(event_row, "skipped")
    after = db.get_calendar_event_by_email(email_row)[0]
    assert after["status"] == "skipped"
    assert after["google_event_id"] == "prev"


def test_insert_calendar_event_rejects_unknown_status():
    email_row = _make_email("cal_bad")
    with pytest.raises(ValueError, match="Invalid calendar event status"):
        db.insert_calendar_event(email_row, "x", status="confused")


def test_update_calendar_event_status_rejects_unknown_status():
    email_row = _make_email("cal_bad2")
    event_row = db.insert_calendar_event(email_row, "x")
    with pytest.raises(ValueError, match="Invalid calendar event status"):
        db.update_calendar_event_status(event_row, "definitely-not-real")


def test_get_calendar_event_by_id_round_trips():
    email_row = _make_email("cal_by_id")
    event_row = db.insert_calendar_event(email_row, "Standup", event_date="2026-06-01")
    got = db.get_calendar_event_by_id(event_row)
    assert got is not None
    assert got["id"] == event_row
    assert got["title"] == "Standup"


def test_get_calendar_event_by_id_returns_none_when_missing():
    assert db.get_calendar_event_by_id(99999) is None


def test_get_calendar_events_by_status_filters_and_orders():
    email_row = _make_email("cal_by_status")
    db.insert_calendar_event(email_row, "Later", event_date="2026-06-02", event_time="09:00")
    db.insert_calendar_event(email_row, "Earlier", event_date="2026-06-01", event_time="09:00")
    created_row = db.insert_calendar_event(email_row, "Already done")
    db.update_calendar_event_status(created_row, "created", google_event_id="g1")

    detected = db.get_calendar_events_by_status("detected")
    assert [e["title"] for e in detected] == ["Earlier", "Later"]
    created = db.get_calendar_events_by_status("created")
    assert [e["title"] for e in created] == ["Already done"]


def test_get_calendar_events_by_status_rejects_unknown_status():
    with pytest.raises(ValueError, match="Invalid calendar event status"):
        db.get_calendar_events_by_status("nonsense")


def test_init_db_backfills_calendar_events_status(monkeypatch):
    """A DB created before Week 4 (calendar_events with no status column) must
    migrate cleanly when init_db runs again."""
    fd, legacy_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        legacy = sqlite3.connect(legacy_path)
        legacy.executescript("""
            CREATE TABLE emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gmail_message_id TEXT UNIQUE NOT NULL,
                thread_id TEXT,
                sender TEXT NOT NULL,
                subject TEXT,
                body TEXT,
                snippet TEXT,
                received_date TEXT,
                ai_summary TEXT,
                category TEXT,
                sentiment TEXT,
                action_required TEXT,
                urgency_score INTEGER,
                is_read INTEGER DEFAULT 0,
                is_archived INTEGER DEFAULT 0,
                is_starred INTEGER DEFAULT 0,
                processed_at TEXT,
                notified_at TEXT,
                created_at TEXT
            );
            CREATE TABLE draft_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER NOT NULL,
                tone TEXT NOT NULL,
                draft_text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                was_sent INTEGER DEFAULT 0,
                sent_at TEXT,
                created_at TEXT
            );
            CREATE TABLE calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER NOT NULL,
                google_event_id TEXT,
                title TEXT NOT NULL,
                event_date TEXT,
                event_time TEXT,
                duration_minutes INTEGER,
                participants TEXT,
                location TEXT,
                created_at TEXT,
                FOREIGN KEY (email_id) REFERENCES emails(id)
            );
            """)
        legacy.commit()
        legacy.close()

        monkeypatch.setenv("DATABASE_PATH", legacy_path)
        reloaded = importlib.reload(db)
        reloaded.init_db()

        check = reloaded.get_connection()
        try:
            cols = {r["name"] for r in check.execute("PRAGMA table_info(calendar_events)")}
        finally:
            check.close()
        assert "status" in cols
    finally:
        try:
            os.unlink(legacy_path)
        except PermissionError:
            pass
