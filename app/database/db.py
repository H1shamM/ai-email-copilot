import os
import sqlite3
from datetime import datetime

DATABASE_PATH = os.getenv("DATABASE_PATH", "email_assistant.db")


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gmail_message_id TEXT UNIQUE NOT NULL,
            thread_id TEXT,
            sender TEXT NOT NULL,
            subject TEXT,
            body TEXT,
            snippet TEXT,
            received_date TEXT,

            -- AI Analysis
            ai_summary TEXT,
            category TEXT,
            sentiment TEXT,
            action_required TEXT,
            urgency_score INTEGER,

            -- Status
            is_read INTEGER DEFAULT 0,
            is_archived INTEGER DEFAULT 0,
            is_starred INTEGER DEFAULT 0,

            -- Metadata
            processed_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_gmail_id ON emails(gmail_message_id);
        CREATE INDEX IF NOT EXISTS idx_category ON emails(category);
        CREATE INDEX IF NOT EXISTS idx_received_date ON emails(received_date);

        CREATE TABLE IF NOT EXISTS draft_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id INTEGER NOT NULL,
            tone TEXT NOT NULL,
            draft_text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            was_sent INTEGER DEFAULT 0,
            sent_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (email_id) REFERENCES emails(id)
        );

        CREATE INDEX IF NOT EXISTS idx_draft_email_id ON draft_replies(email_id);
        CREATE INDEX IF NOT EXISTS idx_draft_status ON draft_replies(status);

        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id INTEGER NOT NULL,
            google_event_id TEXT,
            title TEXT NOT NULL,
            event_date TEXT,
            event_time TEXT,
            duration_minutes INTEGER,
            participants TEXT,
            location TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (email_id) REFERENCES emails(id)
        );

        CREATE TABLE IF NOT EXISTS followups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id INTEGER NOT NULL,
            remind_at TEXT NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            snoozed_until TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (email_id) REFERENCES emails(id)
        );

        CREATE TABLE IF NOT EXISTS user_preferences (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS telegram_users (
            chat_id INTEGER PRIMARY KEY,
            created_at TEXT DEFAULT (datetime('now')),
            last_seen_at TEXT DEFAULT (datetime('now'))
        );
    """)

    # Backfill the draft_replies.status column for DBs created before Story C.
    existing_cols = {r["name"] for r in conn.execute("PRAGMA table_info(draft_replies)").fetchall()}
    if "status" not in existing_cols:
        conn.execute("ALTER TABLE draft_replies ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
        conn.commit()

    conn.close()


def insert_email(email_data: dict) -> int:
    """Insert an email and return its row id. Skips duplicates."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO emails
               (gmail_message_id, thread_id, sender, subject, body, snippet, received_date)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                email_data["id"],
                email_data.get("thread_id"),
                email_data.get("sender"),
                email_data.get("subject"),
                email_data.get("body"),
                email_data.get("snippet"),
                email_data.get("date"),
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_analysis(gmail_message_id: str, analysis: dict):
    """Store AI analysis results for an email."""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE emails
               SET ai_summary = ?, category = ?, sentiment = ?,
                   action_required = ?, urgency_score = ?,
                   processed_at = ?
               WHERE gmail_message_id = ?""",
            (
                analysis.get("summary"),
                analysis.get("category"),
                analysis.get("sentiment"),
                analysis.get("action_required"),
                analysis.get("urgency_score"),
                datetime.now().isoformat(),
                gmail_message_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_email_by_gmail_id(gmail_message_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM emails WHERE gmail_message_id = ?", (gmail_message_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_email_by_row_id(row_id: int) -> dict | None:
    """Look up a single email row by its sqlite rowid (the int shown in /inbox)."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM emails WHERE id = ?", (row_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_recent_emails(limit: int = 50) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM emails ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_unprocessed_emails() -> list[dict]:
    """Get emails that haven't been analyzed yet."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM emails WHERE processed_at IS NULL").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


DRAFT_STATUSES = {"pending", "approved", "sent", "skipped", "edited"}


def insert_draft_reply(email_id: int, tone: str, draft_text: str) -> int:
    """Insert a new pending draft and return its row id."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO draft_replies (email_id, tone, draft_text, status)
               VALUES (?, ?, ?, 'pending')""",
            (email_id, tone, draft_text),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_drafts_for_email(email_id: int) -> list[dict]:
    """Return the most recent draft per tone for the email."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM draft_replies
               WHERE id IN (
                   SELECT MAX(id) FROM draft_replies
                   WHERE email_id = ?
                   GROUP BY tone
               )
               ORDER BY tone""",
            (email_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_draft_by_id(draft_id: int) -> dict | None:
    """Look up a single draft by its row id."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM draft_replies WHERE id = ?", (draft_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_draft_status(
    draft_id: int,
    status: str,
    *,
    draft_text: str | None = None,
    mark_sent: bool = False,
) -> None:
    """Transition a draft to a new status; optionally overwrite text or stamp sent_at."""
    if status not in DRAFT_STATUSES:
        raise ValueError(f"Invalid draft status {status!r}; allowed: {sorted(DRAFT_STATUSES)}")
    conn = get_connection()
    try:
        if mark_sent:
            conn.execute(
                """UPDATE draft_replies
                   SET status = ?, was_sent = 1, sent_at = ?
                   WHERE id = ?""",
                (status, datetime.now().isoformat(), draft_id),
            )
        elif draft_text is not None:
            conn.execute(
                "UPDATE draft_replies SET status = ?, draft_text = ? WHERE id = ?",
                (status, draft_text, draft_id),
            )
        else:
            conn.execute(
                "UPDATE draft_replies SET status = ? WHERE id = ?",
                (status, draft_id),
            )
        conn.commit()
    finally:
        conn.close()


def get_or_create_telegram_user(chat_id: int) -> dict:
    """Insert the chat_id if missing, bump last_seen_at, return the row."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO telegram_users (chat_id) VALUES (?)",
            (chat_id,),
        )
        conn.execute(
            "UPDATE telegram_users SET last_seen_at = ? WHERE chat_id = ?",
            (datetime.now().isoformat(), chat_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM telegram_users WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()
