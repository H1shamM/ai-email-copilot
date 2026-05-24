"""Telegram bot command handlers + single-user auth guard."""

import asyncio
import logging
import os
from functools import wraps

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.ai import agent
from app.ai.analyzer import analyze_email
from app.ai.meeting_detector import maybe_detect_meeting
from app.ai.reply_generator import generate_replies, regenerate_one
from app.calendar import scheduler
from app.database import db
from app.gmail.service import get_recent_emails as gmail_fetch_recent
from app.gmail.service import is_no_reply_sender
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
    "/schedule - create calendar events from detected meetings\n"
    "/agent <text> - run a natural-language request through the agent\n"
    "/pause - stop push notifications\n"
    "/resume - start push notifications\n"
    "/help - show this message"
)

# Telegram convention: lowercase descriptions, ≤ 60 chars to stay readable in
# the popup. set_my_commands overwrites — re-running on every startup is safe
# and keeps the list in sync with whatever this module declares.
COMMANDS: list[BotCommand] = [
    BotCommand("start", "show welcome message"),
    BotCommand("help", "show available commands"),
    BotCommand("unread", "list unread emails from gmail"),
    BotCommand("analyze", "analyze emails with claude"),
    BotCommand("inbox", "show recently analyzed emails"),
    BotCommand("reply", "draft replies — usage: /reply <id>"),
    BotCommand("schedule", "create calendar events from detected meetings"),
    BotCommand("agent", "run a natural-language request through the agent"),
    BotCommand("pause", "pause push notifications"),
    BotCommand("resume", "resume push notifications"),
]


async def set_bot_commands(application: Application) -> None:
    """Register the command list so Telegram shows a popup when the user types /."""
    try:
        await application.bot.set_my_commands(COMMANDS)
    except Exception:  # noqa: BLE001 — non-fatal cosmetic registration; bot still works without it
        logger.warning("set_my_commands failed; / popup may be empty until next restart")


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


async def _typing(update: Update) -> None:
    """Show 'Bot is typing…' so the user gets immediate feedback on long ops.

    Telegram auto-clears the indicator after ~5 seconds; for longer commands
    we also send a placeholder message that gets replaced by the real result.
    Failures are swallowed — this is purely cosmetic.
    """
    try:
        await update.effective_chat.send_chat_action(ChatAction.TYPING)
    except Exception:  # noqa: BLE001
        logger.debug("send_chat_action failed; continuing without typing indicator")


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
    await _typing(update)
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
    await _typing(update)
    pending = db.get_unprocessed_emails()
    if not pending:
        await update.message.reply_text("No emails to analyze.")
        return

    await update.message.reply_text(
        f"🔎 Analyzing {len(pending)} email{'s' if len(pending) != 1 else ''}… "
        f"this can take ~{max(2, len(pending) * 3)}s."
    )

    blocks: list[str] = []
    for email in pending:
        await _typing(update)
        analysis = await asyncio.to_thread(analyze_email, email)
        if not analysis:
            blocks.append(
                f"⚠️ *\\#{email.get('id', '?')}* "
                f"{escape_markdown_v2(email.get('sender') or 'Unknown')} — analysis failed"
            )
            continue
        db.update_analysis(email["gmail_message_id"], analysis)
        await asyncio.to_thread(maybe_detect_meeting, email, analysis)
        blocks.append(format_analysis_entry(email, analysis))

    if blocks:
        blocks.append("_Tip:_ use `/reply <id>` with one of the `#` numbers above\\.")
    await _send_chunks(update, blocks, "No emails to analyze.")


@authorized_only
async def inbox(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the most recent analyzed emails from the DB with priority indicators."""
    await _typing(update)
    rows = db.get_recent_emails(limit=INBOX_DEFAULT_LIMIT)
    analyzed = [row for row in rows if row.get("processed_at")]
    blocks = [format_inbox_entry(row) for row in analyzed]
    if blocks:
        blocks.append("_Tip:_ use `/reply <id>` with one of the `#` numbers above\\.")
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


async def _run_reply_flow(update: Update, email_id: int) -> None:
    """Generate 3 drafts for email_id, persist, and post with action keyboard.

    Uses `effective_chat.send_message` so it works identically from `/reply <id>`
    and from the notification's "Generate Reply" button (PTB freezes Update
    objects after deserialization, so mutating `update.message` is unsafe).
    """
    chat = update.effective_chat

    email = db.get_email_by_row_id(email_id)
    if not email:
        await chat.send_message(f"No email with id {email_id}.")
        return
    if not email.get("processed_at"):
        await chat.send_message(f"Email {email_id} hasn't been analyzed yet — run /analyze first.")
        return
    if is_no_reply_sender(email.get("sender")):
        await chat.send_message(
            f"✋ {email.get('sender') or 'This sender'} is a no-reply address — "
            "a reply would bounce, so I didn't draft one."
        )
        return

    await _typing(update)
    await chat.send_message("✍️ Drafting 3 replies… ~10s.")
    await _typing(update)
    replies = await asyncio.to_thread(generate_replies, email)
    if not replies:
        await chat.send_message("Couldn't draft replies — try again in a moment.")
        return

    drafts: list[dict] = []
    for tone, text in replies.items():
        draft_id = db.insert_draft_reply(email_id, tone, text)
        drafts.append(db.get_draft_by_id(draft_id))

    body = format_drafts_message(email, drafts)
    keyboard = _build_reply_keyboard(drafts, email_id)
    for chunk in chunk_messages([body]):
        try:
            await chat.send_message(
                chunk,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=keyboard,
            )
        except Exception:  # noqa: BLE001
            # MarkdownV2 escaping is fiddly; fall back to plain text so the
            # user always sees the drafts even if a stray reserved char slips
            # through escape_markdown_v2.
            logger.exception("MarkdownV2 send failed; falling back to plain text")
            await chat.send_message(chunk, reply_markup=keyboard)


@authorized_only
async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/reply <email_id>` — parse args, then run the shared draft flow."""
    args = context.args or []
    if not args or not args[0].isdigit():
        await update.effective_chat.send_message("Usage: /reply <email_id>")
        return
    await _run_reply_flow(update, int(args[0]))


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
    await query.answer("Sending…")
    parsed = _parse_callback(query.data or "")
    if parsed is None or parsed[0] != "approve":
        return
    _, draft_id = parsed
    await _typing(update)
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
    if is_no_reply_sender(email.get("sender")):
        await update.effective_chat.send_message(
            "✋ That email is from a no-reply address — a reply would bounce, so I didn't send it."
        )
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
    await _typing(update)
    await update.message.reply_text("✍️ Sending edited reply…")
    await _send_draft(update, context, draft_id, source="edit")
    return -1


@authorized_only
async def cb_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Skip All — mark every draft for this email as skipped, no Gmail call."""
    query = update.callback_query
    await query.answer("Skipped")
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
    await query.answer("Regenerating…")
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

    await _typing(update)
    new_text = await asyncio.to_thread(regenerate_one, email, draft["tone"])
    if not new_text:
        await update.effective_chat.send_message(f"Regenerate failed for {draft['tone']}.")
        return
    db.update_draft_status(draft_id, "pending", draft_text=new_text)
    await update.effective_chat.send_message(
        f"🔄 New {draft['tone']} draft saved — tap Approve when ready."
    )


@authorized_only
async def cb_notify_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Notification → ✍ Generate Reply: run the shared draft flow."""
    query = update.callback_query
    await query.answer("Drafting…")
    parsed = _parse_callback(query.data or "", prefix="n")
    if parsed is None or parsed[0] != "reply":
        return
    _, email_row_id = parsed
    await _run_reply_flow(update, email_row_id)


@authorized_only
async def cb_notify_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Notification → ✅ Mark Done: archive+read in DB and edit the message."""
    query = update.callback_query
    await query.answer("Done")
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


def _format_schedule_entry(event: dict) -> str:
    """Plain-text summary of a detected event for the /schedule list."""
    lines = [f"#{event['id']} · {event.get('title') or 'Untitled meeting'}"]
    lines.append(f"🗓 {event.get('event_date')} {event.get('event_time')}")
    duration = event.get("duration_minutes") or scheduler.DEFAULT_DURATION_MINUTES
    lines.append(f"⏱ {duration} min")
    if event.get("participants"):
        lines.append(f"👥 {event['participants']}")
    if event.get("location"):
        lines.append(f"📍 {event['location']}")
    return "\n".join(lines)


def _build_schedule_keyboard(event_id: int) -> InlineKeyboardMarkup:
    """Create/Skip keyboard for one detected event."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Create", callback_data=f"s:create:{event_id}"),
                InlineKeyboardButton("⏭ Skip", callback_data=f"s:skip:{event_id}"),
            ]
        ]
    )


@authorized_only
async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/schedule` — list detected meetings with a concrete date+time to create."""
    chat = update.effective_chat
    events = db.get_calendar_events_by_status("detected")
    schedulable = [e for e in events if e.get("event_date") and e.get("event_time")]
    if not schedulable:
        await chat.send_message("No meetings to schedule.")
        return
    for event in schedulable:
        await chat.send_message(
            _format_schedule_entry(event),
            reply_markup=_build_schedule_keyboard(event["id"]),
        )


@authorized_only
async def cb_schedule_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create button — block on freebusy conflict, else insert + mark created."""
    query = update.callback_query
    await query.answer("Checking…")
    parsed = _parse_callback(query.data or "", prefix="s")
    if parsed is None or parsed[0] != "create":
        return
    _, event_id = parsed
    event = db.get_calendar_event_by_id(event_id)
    if event is None:
        await update.effective_chat.send_message("That event no longer exists.")
        return
    if event["status"] in ("created", "skipped"):
        await update.effective_chat.send_message(f"Event already {event['status']}.")
        return

    if scheduler.has_conflict(event):
        await update.effective_chat.send_message(
            "⚠ Conflicts with an existing calendar event — not created. "
            "Tap Skip, or free up the slot and try again."
        )
        return

    try:
        google_event_id = scheduler.create_event(event)
    except Exception as exc:  # noqa: BLE001 — surface a generic failure to the user
        logger.exception("Calendar insert failed for event=%s", event_id)
        db.update_calendar_event_status(event_id, "failed")
        await update.effective_chat.send_message(f"Create failed: {exc}")
        return

    db.update_calendar_event_status(event_id, "created", google_event_id=google_event_id)
    await update.effective_chat.send_message(
        f"✅ Event created: {event.get('title') or 'meeting'}."
    )


@authorized_only
async def cb_schedule_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Skip button — mark the detected event skipped, no Calendar call."""
    query = update.callback_query
    await query.answer("Skipped")
    parsed = _parse_callback(query.data or "", prefix="s")
    if parsed is None or parsed[0] != "skip":
        return
    _, event_id = parsed
    event = db.get_calendar_event_by_id(event_id)
    if event is None:
        await update.effective_chat.send_message("That event no longer exists.")
        return
    if event["status"] in ("created", "skipped"):
        await update.effective_chat.send_message(f"Event already {event['status']}.")
        return
    db.update_calendar_event_status(event_id, "skipped")
    await update.effective_chat.send_message("⏭ Skipped.")


@authorized_only
async def agent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/agent <instruction>` — run a natural-language request through the agent."""
    chat = update.effective_chat
    instruction = " ".join(context.args or []).strip()
    if not instruction:
        await chat.send_message("Usage: /agent <what you want done>")
        return

    await _typing(update)
    await chat.send_message("🤖 Working on it…")
    await _typing(update)
    try:
        text, pending = await asyncio.to_thread(agent.run_agent, instruction)
    except Exception as exc:  # noqa: BLE001 — surface a generic failure to the user
        logger.exception("Agent run failed")
        await chat.send_message(f"Agent failed: {exc}")
        return

    if not pending:
        await chat.send_message(text or "Done — nothing to do.")
        return

    context.user_data["agent_pending"] = pending
    lines = ["Proposed actions (approve to run):"]
    lines += [f"{i}. {agent.describe_action(a)}" for i, a in enumerate(pending, 1)]
    if text:
        lines += ["", text]
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data="a:approve"),
                InlineKeyboardButton("✖ Cancel", callback_data="a:cancel"),
            ]
        ]
    )
    await chat.send_message("\n".join(lines), reply_markup=keyboard)


@authorized_only
async def cb_agent_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Approve — execute every queued agent action in order, report each result."""
    query = update.callback_query
    await query.answer("Running…")
    pending = context.user_data.pop("agent_pending", None)
    if not pending:
        await update.effective_chat.send_message("No pending actions.")
        return
    results = []
    for action in pending:
        try:
            results.append(f"✅ {agent.execute_action(action)}")
        except Exception as exc:  # noqa: BLE001 — one failure shouldn't abort the rest
            logger.exception("Agent action failed: %s", action.get("name"))
            results.append(f"⚠ {action.get('name')} failed: {exc}")
    await update.effective_chat.send_message("\n".join(results))


@authorized_only
async def cb_agent_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel — discard the queued agent actions without running anything."""
    query = update.callback_query
    await query.answer("Cancelled")
    context.user_data.pop("agent_pending", None)
    await update.effective_chat.send_message("✖ Cancelled — nothing was done.")


@authorized_only
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all for unrecognized /commands so the user isn't left guessing."""
    await update.message.reply_text("Unknown command. Send /help to see what I can do.")


@authorized_only
async def fallback_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all for plain (non-command) text so the bot always responds."""
    await update.message.reply_text(
        "I only respond to commands. Send /help to see them, "
        "or use /agent <text> to ask in natural language."
    )


def register(application: Application) -> None:
    """Register all command handlers on the given Application."""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("unread", unread))
    application.add_handler(CommandHandler("analyze", analyze))
    application.add_handler(CommandHandler("inbox", inbox))
    application.add_handler(CommandHandler("reply", reply_command))
    application.add_handler(CommandHandler("schedule", schedule_command))
    application.add_handler(CommandHandler("agent", agent_command))
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
    application.add_handler(CallbackQueryHandler(cb_schedule_create, pattern=r"^s:create:\d+$"))
    application.add_handler(CallbackQueryHandler(cb_schedule_skip, pattern=r"^s:skip:\d+$"))
    application.add_handler(CallbackQueryHandler(cb_agent_approve, pattern=r"^a:approve$"))
    application.add_handler(CallbackQueryHandler(cb_agent_cancel, pattern=r"^a:cancel$"))

    # Fallbacks LAST so they never shadow known commands or the edit conversation:
    # an unrecognized /command, then any plain (non-command) text.
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_text))
