"""Telegram bot command handlers + single-user auth guard."""

import logging
import os
from functools import wraps

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from app.ai.analyzer import analyze_email
from app.database import db
from app.gmail.service import get_recent_emails as gmail_fetch_recent
from app.telegram.formatting import (
    chunk_messages,
    escape_markdown_v2,
    format_analysis_entry,
    format_inbox_entry,
    format_unread_entry,
)

INBOX_DEFAULT_LIMIT = 10
UNREAD_DEFAULT_LIMIT = 20

logger = logging.getLogger(__name__)

WELCOME = (
    "Welcome to AI Email Copilot.\n\n"
    "Commands:\n"
    "/unread - list unread emails\n"
    "/analyze - run AI analysis on unprocessed emails\n"
    "/inbox - show last analyzed emails\n"
    "/reply <id> - draft a reply to an email\n"
    "/help - show this message"
)


def _is_authorized(chat_id: int | None) -> bool:
    """Check whether chat_id matches TELEGRAM_AUTHORIZED_CHAT_ID env var."""
    if chat_id is None:
        return False
    authorized_id = os.getenv("TELEGRAM_AUTHORIZED_CHAT_ID")
    if not authorized_id:
        return False
    try:
        return int(authorized_id) == chat_id
    except ValueError:
        return False


def authorized_only(handler):
    """Drop updates from any chat_id other than TELEGRAM_AUTHORIZED_CHAT_ID."""

    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        chat_id = chat.id if chat else None
        if not _is_authorized(chat_id):
            logger.info("Dropped update from unauthorized chat_id=%s", chat_id)
            return None
        db.get_or_create_telegram_user(chat_id)
        return await handler(update, context)

    return wrapper


@authorized_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /start with the welcome message."""
    await update.message.reply_text(WELCOME)


@authorized_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /help with the welcome message."""
    await update.message.reply_text(WELCOME)


async def _send_chunks(update: Update, blocks: list[str], empty_message: str) -> None:
    """Render blocks via chunk_messages and send each as MarkdownV2."""
    if not blocks:
        await update.message.reply_text(empty_message)
        return
    for chunk in chunk_messages(blocks):
        await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN_V2)


@authorized_only
async def unread(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch unread emails from Gmail and reply with a numbered list."""
    try:
        emails = gmail_fetch_recent(max_results=UNREAD_DEFAULT_LIMIT, unread_only=True)
    except RuntimeError as exc:
        logger.exception("Gmail fetch failed for /unread")
        await update.message.reply_text(f"Gmail error: {exc}")
        return
    blocks = [format_unread_entry(email, i + 1) for i, email in enumerate(emails)]
    await _send_chunks(update, blocks, "No unread emails.")


@authorized_only
async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run Claude on every unprocessed email in the DB and reply with results."""
    pending = db.get_unprocessed_emails()
    blocks: list[str] = []
    for index, email in enumerate(pending, start=1):
        analysis = analyze_email(email)
        if not analysis:
            blocks.append(
                f"⚠️ *{index}\\.* {escape_markdown_v2(email.get('sender') or 'Unknown')} "
                f"— analysis failed"
            )
            continue
        db.update_analysis(email["gmail_message_id"], analysis)
        blocks.append(format_analysis_entry(email, analysis, index))

    await _send_chunks(update, blocks, "No emails to analyze.")


@authorized_only
async def inbox(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the most recent analyzed emails from the DB with priority indicators."""
    rows = db.get_recent_emails(limit=INBOX_DEFAULT_LIMIT)
    analyzed = [row for row in rows if row.get("processed_at")]
    blocks = [format_inbox_entry(row, i + 1) for i, row in enumerate(analyzed)]
    await _send_chunks(update, blocks, "No analyzed emails yet.")


def register(application: Application) -> None:
    """Register all command handlers on the given Application."""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("unread", unread))
    application.add_handler(CommandHandler("analyze", analyze))
    application.add_handler(CommandHandler("inbox", inbox))
