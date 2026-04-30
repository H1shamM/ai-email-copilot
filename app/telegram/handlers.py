"""Telegram bot command handlers + single-user auth guard."""

import logging
import os
from functools import wraps

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.database import db

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


def register(application: Application) -> None:
    """Register all command handlers on the given Application."""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
