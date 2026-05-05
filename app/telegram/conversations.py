"""ConversationHandler for the multi-turn 'Edit draft' flow."""

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

EDIT_TIMEOUT_SECONDS = 300

WAITING_FOR_TEXT = 1


async def edit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User typed /cancel during an edit; clear state and confirm."""
    context.user_data.pop("editing_draft_id", None)
    if update.message:
        await update.message.reply_text("Edit cancelled.")
    return ConversationHandler.END


async def edit_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Conversation idled past EDIT_TIMEOUT_SECONDS — drop state."""
    context.user_data.pop("editing_draft_id", None)
    return ConversationHandler.END


def build_edit_handler(start_callback, save_callback) -> ConversationHandler:
    """Wire the Edit conversation: button press → wait for text → save."""
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_callback, pattern=r"^r:edit:\d+$")],
        states={
            WAITING_FOR_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_callback),
                CommandHandler("cancel", edit_cancel),
            ],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, edit_timeout)],
        },
        fallbacks=[CommandHandler("cancel", edit_cancel)],
        conversation_timeout=EDIT_TIMEOUT_SECONDS,
        per_message=False,
    )
