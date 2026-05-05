"""Unit tests for the Edit ConversationHandler helpers."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ConversationHandler

from app.telegram import conversations


@pytest.mark.asyncio
async def test_edit_cancel_clears_state_and_replies():
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.user_data = {"editing_draft_id": 7, "other": "keep"}

    state = await conversations.edit_cancel(update, context)

    assert state == ConversationHandler.END
    assert "editing_draft_id" not in context.user_data
    assert context.user_data["other"] == "keep"
    update.message.reply_text.assert_awaited_once_with("Edit cancelled.")


@pytest.mark.asyncio
async def test_edit_cancel_handles_missing_message():
    """Cancel from a callback (no .message) must still drop state cleanly."""
    update = MagicMock()
    update.message = None
    context = MagicMock()
    context.user_data = {"editing_draft_id": 1}

    state = await conversations.edit_cancel(update, context)

    assert state == ConversationHandler.END
    assert "editing_draft_id" not in context.user_data


@pytest.mark.asyncio
async def test_edit_timeout_clears_state():
    update = MagicMock()
    context = MagicMock()
    context.user_data = {"editing_draft_id": 3}

    state = await conversations.edit_timeout(update, context)

    assert state == ConversationHandler.END
    assert "editing_draft_id" not in context.user_data


def test_build_edit_handler_returns_conversation_handler():
    handler = conversations.build_edit_handler(
        start_callback=AsyncMock(), save_callback=AsyncMock()
    )
    assert isinstance(handler, ConversationHandler)
