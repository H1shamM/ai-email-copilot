"""Telegram bot Application instance + lifecycle helpers."""

import os

from telegram import Update
from telegram.ext import Application

_application: Application | None = None


def get_application() -> Application:
    """Build (lazily) and return the Telegram Application singleton."""
    global _application
    if _application is None:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
        _application = Application.builder().token(token).build()
        from app.telegram import handlers

        handlers.register(_application)
    return _application


async def initialize() -> None:  # pragma: no cover
    """Initialize the Application; call from FastAPI startup."""
    app = get_application()
    await app.initialize()


async def shutdown() -> None:  # pragma: no cover
    """Shut down the Application; call from FastAPI shutdown."""
    global _application
    if _application is not None:
        await _application.shutdown()
        _application = None


async def process_update_from_json(payload: dict) -> None:  # pragma: no cover
    """Parse a webhook payload and dispatch it through registered handlers."""
    app = get_application()
    update = Update.de_json(payload, app.bot)
    await app.process_update(update)
