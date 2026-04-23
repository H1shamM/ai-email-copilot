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
            was_sent INTEGER DEFAULT 0,
            sent_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (email_id) REFERENCES emails(id)
        );

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
    """)
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
