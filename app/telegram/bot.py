"""Telegram bot Application instance + lifecycle helpers."""

import os

from telegram import Update
from telegram.ext import Application
from telegram.request import HTTPXRequest

_application: Application | None = None

# PTB's default connect_timeout (~5s) is too short on cold-start Windows + httpx,
# where TLS handshake to api.telegram.org can take 8-15s. Bumping to 30s avoids
# spurious TimedOut errors on FastAPI startup without affecting steady-state perf.
_CONNECT_TIMEOUT = 30.0
_READ_TIMEOUT = 30.0
_WRITE_TIMEOUT = 30.0
_POOL_TIMEOUT = 5.0


def get_application() -> Application:
    """Build (lazily) and return the Telegram Application singleton."""
    global _application
    if _application is None:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
        request = HTTPXRequest(
            connect_timeout=_CONNECT_TIMEOUT,
            read_timeout=_READ_TIMEOUT,
            write_timeout=_WRITE_TIMEOUT,
            pool_timeout=_POOL_TIMEOUT,
        )
        get_updates_request = HTTPXRequest(
            connect_timeout=_CONNECT_TIMEOUT,
            read_timeout=_READ_TIMEOUT,
            write_timeout=_WRITE_TIMEOUT,
            pool_timeout=_POOL_TIMEOUT,
        )
        _application = (
            Application.builder()
            .token(token)
            .request(request)
            .get_updates_request(get_updates_request)
            .build()
        )
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
