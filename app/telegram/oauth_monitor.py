"""Periodic, non-interactive Gmail OAuth health check with proactive alerting.

Google revokes Testing-app refresh tokens ~7 days after issuance, which silently
breaks every Gmail/Calendar command until the token is re-bootstrapped. This job
checks the token on an interval and DMs the authorized user the moment it goes
bad, so re-auth is a deliberate response to an alert rather than a surprise
mid-command. It cannot keep the token alive — only publishing the OAuth app does
that — it just surfaces the failure early. Alerts are edge-triggered (once per
outage), with a one-off "restored" message when the token is healthy again.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.gmail.auth import gmail_token_status

if TYPE_CHECKING:
    from telegram.ext import Application

DEFAULT_INTERVAL_HOURS = 24

JOB_ID = "oauth_health"

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
_alerted = False  # edge-trigger: alert once per outage, not on every tick


def _get_scheduler() -> AsyncIOScheduler:
    """Lazy scheduler so APScheduler doesn't grab a loop before FastAPI has one."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def _authorized_chat_id() -> int | None:
    """The single authorized chat to notify, or None if unset/invalid."""
    raw = os.getenv("TELEGRAM_AUTHORIZED_CHAT_ID")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


async def check_and_alert(application: "Application") -> bool:
    """Run one OAuth health check; alert on the healthy↔broken edges. Returns ok."""
    global _alerted
    ok, detail = await asyncio.to_thread(gmail_token_status)
    chat_id = _authorized_chat_id()

    if ok:
        if _alerted and chat_id is not None:
            await _send(application, chat_id, "✅ Gmail authorization restored.")
        _alerted = False
        return True

    logger.warning("Gmail OAuth unhealthy: %s", detail)
    if not _alerted and chat_id is not None:
        sent = await _send(
            application,
            chat_id,
            f"⚠ Gmail authorization expired or revoked ({detail}).\n"
            "Re-run OAuth and redeploy token.pickle — Gmail/Calendar commands "
            "will fail until then.",
        )
        _alerted = sent
    return False


async def _send(application: "Application", chat_id: int, text: str) -> bool:
    """Send a plain-text DM; return True iff Telegram accepted it."""
    try:
        await application.bot.send_message(chat_id=chat_id, text=text)
        return True
    except Exception:  # noqa: BLE001 — log + report not-sent so we retry next tick
        logger.exception("OAuth monitor failed to send Telegram message")
        return False


def start(application: "Application", *, interval_hours: int = DEFAULT_INTERVAL_HOURS) -> None:
    """Start (or replace) the recurring OAuth health-check job."""
    scheduler = _get_scheduler()
    seconds = max(300, int(interval_hours) * 3600)
    scheduler.add_job(
        check_and_alert,
        "interval",
        seconds=seconds,
        kwargs={"application": application},
        id=JOB_ID,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        # First check shortly after boot so a token that died while we were down
        # is surfaced immediately, not one interval later.
        next_run_time=datetime.now() + timedelta(seconds=30),
    )
    if not scheduler.running:
        scheduler.start()
    logger.info("OAuth monitor started (interval=%dh)", interval_hours)


def stop() -> None:
    """Stop the monitor and reset alert state; safe when not running."""
    global _scheduler, _alerted
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
    _alerted = False


def is_enabled_at_boot() -> bool:
    """Whether TELEGRAM_OAUTH_CHECK_ENABLED says to auto-start on app startup."""
    raw = os.getenv("TELEGRAM_OAUTH_CHECK_ENABLED", "true").strip().lower()
    return raw not in ("0", "false", "no", "off")
