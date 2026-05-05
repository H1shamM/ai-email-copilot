"""Background scheduler that proactively notifies on high-priority emails.

Runs inside the FastAPI event loop via APScheduler. Each tick:
  1. Pulls unread mail from Gmail (via the existing service wrapper).
  2. Persists any new rows in SQLite.
  3. Analyzes everything not yet processed.
  4. For every analyzed email at or above the threshold whose `notified_at`
     is NULL, sends a Telegram notification and stamps `notified_at`.

Idempotency lives in the DB: `notified_at` is the gate, so restarts and
overlapping ticks never double-notify the same row.
"""

import logging
import os
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from app.ai.analyzer import analyze_email
from app.database import db
from app.gmail.service import get_recent_emails as gmail_fetch_recent
from app.telegram.formatting import chunk_messages, format_notification

if TYPE_CHECKING:
    from telegram.ext import Application

DEFAULT_INTERVAL_MINUTES = 5
DEFAULT_THRESHOLD = 4
DEFAULT_FETCH_BATCH = 20

JOB_ID = "push_notifications"

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _get_scheduler() -> AsyncIOScheduler:
    """Lazy scheduler so APScheduler doesn't get a loop before FastAPI has one."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def _build_keyboard(email_row_id: int) -> InlineKeyboardMarkup:
    """Inline keyboard attached to every notification."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✍ Generate Reply", callback_data=f"n:reply:{email_row_id}"),
                InlineKeyboardButton("✅ Mark Done", callback_data=f"n:done:{email_row_id}"),
            ]
        ]
    )


async def _notify_one(application: "Application", chat_id: int, row: dict) -> bool:
    """Send a single notification. Returns True iff Telegram accepted it."""
    body = format_notification(row)
    keyboard = _build_keyboard(row["id"])
    try:
        for chunk in chunk_messages([body]):
            await application.bot.send_message(
                chat_id=chat_id,
                text=chunk,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=keyboard,
            )
    except Exception:  # noqa: BLE001 — log + skip; don't stamp so retry happens next tick
        logger.exception("Telegram send failed for email row=%s", row.get("id"))
        return False
    return True


async def tick(application: "Application", *, threshold: int) -> int:
    """Run one push iteration. Returns the number of notifications sent."""
    chat_id = _authorized_chat_id()
    if chat_id is None:
        logger.warning("TELEGRAM_AUTHORIZED_CHAT_ID unset; skipping push tick")
        return 0

    _ingest_and_analyze()

    candidates = db.get_high_priority_unnotified(threshold)
    sent = 0
    for row in candidates:
        if await _notify_one(application, chat_id, row):
            db.mark_email_notified(row["gmail_message_id"])
            sent += 1
    return sent


def _ingest_and_analyze() -> None:
    """Pull recent unread, persist new rows, analyze the unprocessed."""
    try:
        emails = gmail_fetch_recent(max_results=DEFAULT_FETCH_BATCH, unread_only=True)
    except Exception:  # noqa: BLE001
        logger.exception("Gmail fetch failed during push tick")
        return

    for email in emails:
        db.insert_email(email)

    for pending in db.get_unprocessed_emails():
        analysis = analyze_email(pending)
        if analysis:
            db.update_analysis(pending["gmail_message_id"], analysis)


def _authorized_chat_id() -> int | None:
    raw = os.getenv("TELEGRAM_AUTHORIZED_CHAT_ID")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def start(
    application: "Application",
    *,
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
    threshold: int = DEFAULT_THRESHOLD,
) -> None:
    """Start (or replace) the recurring push job."""
    scheduler = _get_scheduler()
    interval_seconds = max(60, int(interval_minutes) * 60)
    scheduler.add_job(
        tick,
        "interval",
        seconds=interval_seconds,
        kwargs={"application": application, "threshold": threshold},
        id=JOB_ID,
        replace_existing=True,
        misfire_grace_time=interval_seconds // 2,
        coalesce=True,
        max_instances=1,
    )
    if not scheduler.running:
        scheduler.start()
    logger.info("Push scheduler started (interval=%dm, threshold=%d)", interval_minutes, threshold)


def stop() -> None:
    """Stop the scheduler entirely; safe to call when not running."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def pause() -> bool:
    """Pause without tearing down the scheduler. Returns True iff state changed."""
    scheduler = _get_scheduler()
    if not scheduler.running:
        return False
    scheduler.pause()
    return True


def resume() -> bool:
    """Resume a paused scheduler. Returns True iff state changed."""
    scheduler = _get_scheduler()
    if not scheduler.running:
        scheduler.start()
        return True
    if scheduler.state == 2:  # STATE_PAUSED
        scheduler.resume()
        return True
    return False


def is_running() -> bool:
    """Whether the scheduler is currently delivering ticks."""
    if _scheduler is None:
        return False
    return _scheduler.running and _scheduler.state != 2  # not paused


def is_enabled_at_boot() -> bool:
    """Whether TELEGRAM_PUSH_ENABLED says we should auto-start on app startup."""
    raw = os.getenv("TELEGRAM_PUSH_ENABLED", "true").strip().lower()
    return raw not in ("0", "false", "no", "off")
