"""Unit tests for app.telegram.oauth_monitor (no real Gmail / scheduler I/O)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.telegram import oauth_monitor


@pytest.fixture(autouse=True)
def _reset_alert_state(monkeypatch):
    """Each test starts with no outstanding alert."""
    monkeypatch.setattr(oauth_monitor, "_alerted", False)


def _app() -> MagicMock:
    app = MagicMock()
    app.bot.send_message = AsyncMock()
    return app


@pytest.mark.asyncio
async def test_healthy_token_no_alert(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(oauth_monitor, "gmail_token_status", lambda: (True, "valid"))
    app = _app()

    ok = await oauth_monitor.check_and_alert(app)

    assert ok is True
    app.bot.send_message.assert_not_awaited()
    assert oauth_monitor._alerted is False


@pytest.mark.asyncio
async def test_expired_token_alerts_once(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(
        oauth_monitor, "gmail_token_status", lambda: (False, "refresh failed: invalid_grant")
    )
    app = _app()

    ok = await oauth_monitor.check_and_alert(app)

    assert ok is False
    assert oauth_monitor._alerted is True
    app.bot.send_message.assert_awaited_once()
    text = app.bot.send_message.await_args.kwargs["text"]
    assert "expired or revoked" in text
    assert "invalid_grant" in text


@pytest.mark.asyncio
async def test_no_duplicate_alert_while_still_broken(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(oauth_monitor, "_alerted", True)  # already alerted this outage
    monkeypatch.setattr(oauth_monitor, "gmail_token_status", lambda: (False, "still dead"))
    app = _app()

    ok = await oauth_monitor.check_and_alert(app)

    assert ok is False
    app.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovery_sends_restored_then_resets(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(oauth_monitor, "_alerted", True)  # was in an outage
    monkeypatch.setattr(oauth_monitor, "gmail_token_status", lambda: (True, "refreshed"))
    app = _app()

    ok = await oauth_monitor.check_and_alert(app)

    assert ok is True
    assert oauth_monitor._alerted is False
    text = app.bot.send_message.await_args.kwargs["text"]
    assert "restored" in text


@pytest.mark.asyncio
async def test_no_chat_id_skips_send(monkeypatch):
    monkeypatch.delenv("TELEGRAM_AUTHORIZED_CHAT_ID", raising=False)
    monkeypatch.setattr(oauth_monitor, "gmail_token_status", lambda: (False, "dead"))
    app = _app()

    ok = await oauth_monitor.check_and_alert(app)

    assert ok is False
    app.bot.send_message.assert_not_awaited()
    # Without a chat to notify, don't flip the alert flag — retry once we can send.
    assert oauth_monitor._alerted is False


@pytest.mark.asyncio
async def test_send_failure_leaves_alert_unflipped(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    monkeypatch.setattr(oauth_monitor, "gmail_token_status", lambda: (False, "dead"))
    app = _app()
    app.bot.send_message.side_effect = RuntimeError("telegram down")

    ok = await oauth_monitor.check_and_alert(app)

    assert ok is False
    assert oauth_monitor._alerted is False  # so the next tick retries the alert


def test_is_enabled_at_boot_default_true(monkeypatch):
    monkeypatch.delenv("TELEGRAM_OAUTH_CHECK_ENABLED", raising=False)
    assert oauth_monitor.is_enabled_at_boot() is True


@pytest.mark.parametrize("val", ["false", "0", "no", "off", "FALSE"])
def test_is_enabled_at_boot_disabled(monkeypatch, val):
    monkeypatch.setenv("TELEGRAM_OAUTH_CHECK_ENABLED", val)
    assert oauth_monitor.is_enabled_at_boot() is False


@pytest.mark.asyncio
async def test_start_then_stop(monkeypatch):
    monkeypatch.setattr(oauth_monitor, "_scheduler", None)
    app = _app()

    oauth_monitor.start(app, interval_hours=24)
    scheduler = oauth_monitor._get_scheduler()
    assert scheduler.running
    assert scheduler.get_job(oauth_monitor.JOB_ID) is not None

    oauth_monitor.stop()
    assert oauth_monitor._scheduler is None
