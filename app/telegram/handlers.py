"""Telegram bot command handlers + single-user auth guard."""

import logging
import os
from functools import wraps

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from app.ai.analyzer import analyze_email
from app.ai.reply_generator import generate_replies, regenerate_one
from app.database import db
from app.gmail.service import get_recent_emails as gmail_fetch_recent
from app.gmail.service import send_reply as gmail_send_reply
from app.telegram import push as telegram_push
from app.telegram.conversations import WAITING_FOR_TEXT, build_edit_handler
from app.telegram.formatting import (
    chunk_messages,
    escape_markdown_v2,
    format_analysis_entry,
    format_drafts_message,
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
    "/pause - stop push notifications\n"
    "/resume - start push notifications\n"
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


_REPLY_TONES = ("professional", "friendly", "brief")
_TONE_GLYPH = {"professional": "🎩", "friendly": "😊", "brief": "⚡"}


def _build_reply_keyboard(drafts: list[dict], email_id: int) -> InlineKeyboardMarkup:
    """Build the Approve/Edit/Regenerate per tone + Skip All keyboard."""
    rows = []
    by_tone = {d["tone"]: d for d in drafts}
    for tone in _REPLY_TONES:
        draft = by_tone.get(tone)
        if not draft:
            continue
        glyph = _TONE_GLYPH[tone]
        rows.append(
            [
                InlineKeyboardButton(
                    f"{glyph} ✅ Approve", callback_data=f"r:approve:{draft['id']}"
                ),
                InlineKeyboardButton(f"{glyph} ✏ Edit", callback_data=f"r:edit:{draft['id']}"),
                InlineKeyboardButton(f"{glyph} 🔄 Regen", callback_data=f"r:regen:{draft['id']}"),
            ]
        )
    rows.append([InlineKeyboardButton("⏭ Skip all", callback_data=f"r:skip:{email_id}")])
    return InlineKeyboardMarkup(rows)


@authorized_only
async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/reply <email_id>` — generate 3 drafts and post them with action buttons."""
    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /reply <email_id>")
        return
    email_id = int(args[0])

    email = db.get_email_by_row_id(email_id)
    if not email:
        await update.message.reply_text(f"No email with id {email_id}.")
        return
    if not email.get("processed_at"):
        await update.message.reply_text(
            f"Email {email_id} hasn't been analyzed yet — run /analyze first."
        )
        return

    await update.message.reply_text("Drafting replies… this can take a few seconds.")
    replies = generate_replies(email)
    if not replies:
        await update.message.reply_text("Couldn't draft replies — try again in a moment.")
        return

    drafts: list[dict] = []
    for tone, text in replies.items():
        draft_id = db.insert_draft_reply(email_id, tone, text)
        drafts.append(db.get_draft_by_id(draft_id))

    body = format_drafts_message(email, drafts)
    keyboard = _build_reply_keyboard(drafts, email_id)
    for chunk in chunk_messages([body]):
        await update.message.reply_text(
            chunk,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=keyboard,
        )


def _parse_callback(data: str, prefix: str = "r") -> tuple[str, int] | None:
    """Parse `<prefix>:<action>:<id>` callback data; return (action, id) or None."""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != prefix or not parts[2].isdigit():
        return None
    return parts[1], int(parts[2])


@authorized_only
async def cb_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User tapped Approve — send via Gmail and mark draft sent."""
    query = update.callback_query
    await query.answer()
    parsed = _parse_callback(query.data or "")
    if parsed is None or parsed[0] != "approve":
        return
    _, draft_id = parsed
    await _send_draft(update, context, draft_id, source="approve")


async def _send_draft(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    draft_id: int,
    source: str,
) -> None:
    draft = db.get_draft_by_id(draft_id)
    if draft is None:
        await update.effective_chat.send_message("That draft no longer exists.")
        return
    if draft["status"] in ("sent", "skipped"):
        await update.effective_chat.send_message(f"Draft already {draft['status']}.")
        return

    email = db.get_email_by_row_id(draft["email_id"])
    if email is None:
        await update.effective_chat.send_message("Original email not found in DB.")
        return

    try:
        gmail_send_reply(email["thread_id"], email["gmail_message_id"], draft["draft_text"])
    except Exception as exc:  # noqa: BLE001 — surface a generic failure to the user
        logger.exception("Gmail send_reply failed (source=%s, draft=%s)", source, draft_id)
        await update.effective_chat.send_message(f"Send failed: {exc}")
        return

    db.update_draft_status(draft_id, "sent", mark_sent=True)
    await update.effective_chat.send_message(f"✅ Reply sent ({draft['tone']}).")


@authorized_only
async def cb_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Edit button — stash the draft id and wait for the user's revised text."""
    query = update.callback_query
    await query.answer()
    parsed = _parse_callback(query.data or "")
    if parsed is None or parsed[0] != "edit":
        return -1  # exits ConversationHandler if it can't parse
    _, draft_id = parsed
    draft = db.get_draft_by_id(draft_id)
    if draft is None:
        await update.effective_chat.send_message("That draft no longer exists.")
        return -1
    context.user_data["editing_draft_id"] = draft_id
    await update.effective_chat.send_message(
        f"Send the revised {draft['tone']} reply (or /cancel to abort)."
    )
    return WAITING_FOR_TEXT


@authorized_only
async def cb_edit_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User typed the revised draft text — overwrite, mark edited, then send."""
    draft_id = context.user_data.pop("editing_draft_id", None)
    if draft_id is None:
        return -1
    new_text = (update.message.text or "").strip()
    if not new_text:
        await update.message.reply_text("Empty message — edit cancelled.")
        return -1
    db.update_draft_status(draft_id, "edited", draft_text=new_text)
    await _send_draft(update, context, draft_id, source="edit")
    return -1


@authorized_only
async def cb_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Skip All — mark every draft for this email as skipped, no Gmail call."""
    query = update.callback_query
    await query.answer()
    parsed = _parse_callback(query.data or "")
    if parsed is None or parsed[0] != "skip":
        return
    _, email_id = parsed
    drafts = db.get_drafts_for_email(email_id)
    for draft in drafts:
        if draft["status"] not in ("sent", "skipped"):
            db.update_draft_status(draft["id"], "skipped")
    await update.effective_chat.send_message("⏭ All drafts skipped.")


@authorized_only
async def cb_regenerate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Regenerate one tone — replace draft_text in place; leave others untouched."""
    query = update.callback_query
    await query.answer()
    parsed = _parse_callback(query.data or "")
    if parsed is None or parsed[0] != "regen":
        return
    _, draft_id = parsed
    draft = db.get_draft_by_id(draft_id)
    if draft is None:
        await update.effective_chat.send_message("That draft no longer exists.")
        return
    email = db.get_email_by_row_id(draft["email_id"])
    if email is None:
        await update.effective_chat.send_message("Original email not found.")
        return

    new_text = regenerate_one(email, draft["tone"])
    if not new_text:
        await update.effective_chat.send_message(f"Regenerate failed for {draft['tone']}.")
        return
    db.update_draft_status(draft_id, "pending", draft_text=new_text)
    await update.effective_chat.send_message(
        f"🔄 New {draft['tone']} draft saved — tap Approve when ready."
    )


@authorized_only
async def cb_notify_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Notification → ✍ Generate Reply: delegate to the Story C /reply flow."""
    query = update.callback_query
    await query.answer()
    parsed = _parse_callback(query.data or "", prefix="n")
    if parsed is None or parsed[0] != "reply":
        return
    _, email_row_id = parsed
    context.args = [str(email_row_id)]
    # reply_command reads update.message.reply_text — for callbacks we route
    # through update.effective_chat instead by patching message onto the update.
    update.message = query.message
    await reply_command(update, context)


@authorized_only
async def cb_notify_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Notification → ✅ Mark Done: archive+read in DB and edit the message."""
    query = update.callback_query
    await query.answer()
    parsed = _parse_callback(query.data or "", prefix="n")
    if parsed is None or parsed[0] != "done":
        return
    _, email_row_id = parsed
    db.mark_email_done(email_row_id)
    try:
        await query.edit_message_text("✅ Done.")
    except Exception:  # noqa: BLE001 — non-fatal if message can't be edited
        logger.exception("Failed to edit notification message for email=%s", email_row_id)
        await update.effective_chat.send_message("✅ Done.")


@authorized_only
async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stop the push scheduler."""
    telegram_push.pause()
    await update.message.reply_text("🔕 Notifications paused.")


@authorized_only
async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resume the push scheduler (or start it if it wasn't running)."""
    telegram_push.resume()
    await update.message.reply_text("🔔 Notifications resumed.")


def register(application: Application) -> None:
    """Register all command handlers on the given Application."""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("unread", unread))
    application.add_handler(CommandHandler("analyze", analyze))
    application.add_handler(CommandHandler("inbox", inbox))
    application.add_handler(CommandHandler("reply", reply_command))
    application.add_handler(CommandHandler("pause", pause_command))
    application.add_handler(CommandHandler("resume", resume_command))

    # Edit conversation must be registered before the bare CallbackQueryHandlers,
    # otherwise the entry-point pattern is shadowed.
    application.add_handler(build_edit_handler(cb_edit_start, cb_edit_save))
    application.add_handler(CallbackQueryHandler(cb_approve, pattern=r"^r:approve:\d+$"))
    application.add_handler(CallbackQueryHandler(cb_skip, pattern=r"^r:skip:\d+$"))
    application.add_handler(CallbackQueryHandler(cb_regenerate, pattern=r"^r:regen:\d+$"))
    application.add_handler(CallbackQueryHandler(cb_notify_reply, pattern=r"^n:reply:\d+$"))
    application.add_handler(CallbackQueryHandler(cb_notify_done, pattern=r"^n:done:\d+$"))
