"""Unit tests for the push scheduler — Telegram + Gmail + Claude all mocked."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.database import db
from app.telegram import push


def _seed_email(
    gmail_id: str,
    *,
    urgency: int | None = None,
    notified: bool = False,
    body: str = "x",
) -> int:
    """Insert + analyze + (optionally) mark notified. Return sqlite rowid."""
    rid = db.insert_email(
        {
            "id": gmail_id,
            "thread_id": "t",
            "sender": "alice@example.com",
            "subject": "s",
            "body": body,
            "snippet": "",
            "date": "2026-05-01",
        }
    )
    if urgency is not None:
        db.update_analysis(
            gmail_id,
            {
                "summary": "sum",
                "category": "Work",
                "sentiment": "Casual",
                "action_required": "Reply",
                "urgency_score": urgency,
            },
        )
    if notified:
        db.mark_email_notified(gmail_id)
    return rid


def _stub_application() -> MagicMock:
    """Application object with bot.send_message as an AsyncMock."""
    app = MagicMock()
    app.bot.send_message = AsyncMock()
    return app


async def _async_noop(*_args, **_kwargs) -> None:
    """Awaitable no-op — used to monkeypatch the now-async _ingest_and_analyze."""
    return None


@pytest.fixture(autouse=True)
def reset_scheduler():
    """Tear down the module-level scheduler between tests."""
    push.stop()
    yield
    push.stop()


def test_get_high_priority_unnotified_filters_correctly():
    _seed_email("low", urgency=2)
    _seed_email("mid", urgency=4)
    _seed_email("high", urgency=9)
    _seed_email("done", urgency=10, notified=True)

    rows = db.get_high_priority_unnotified(threshold=4)
    ids = [r["gmail_message_id"] for r in rows]
    assert ids == ["high", "mid"]  # ordered by urgency DESC


def test_mark_email_notified_stamps_timestamp():
    _seed_email("g", urgency=8)
    db.mark_email_notified("g")
    row = db.get_email_by_gmail_id("g")
    assert row["notified_at"] is not None


def test_mark_email_done_marks_archived_and_read():
    rid = _seed_email("d", urgency=8)
    db.mark_email_done(rid)
    row = db.get_email_by_gmail_id("d")
    assert row["is_archived"] == 1
    assert row["is_read"] == 1


@pytest.mark.asyncio
async def test_tick_sends_only_for_high_priority(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    _seed_email("low", urgency=2)
    _seed_email("hi1", urgency=7)
    _seed_email("hi2", urgency=9)

    monkeypatch.setattr(push, "_ingest_and_analyze", _async_noop)
    app = _stub_application()
    sent = await push.tick(app, threshold=4)

    assert sent == 2
    # All sent rows should now be marked notified
    assert db.get_email_by_gmail_id("hi1")["notified_at"] is not None
    assert db.get_email_by_gmail_id("hi2")["notified_at"] is not None
    assert db.get_email_by_gmail_id("low")["notified_at"] is None
    assert app.bot.send_message.await_count == 2


@pytest.mark.asyncio
async def test_tick_is_idempotent(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    _seed_email("g", urgency=9)
    monkeypatch.setattr(push, "_ingest_and_analyze", _async_noop)
    app = _stub_application()

    first = await push.tick(app, threshold=4)
    second = await push.tick(app, threshold=4)

    assert first == 1
    assert second == 0
    assert app.bot.send_message.await_count == 1


@pytest.mark.asyncio
async def test_tick_does_not_stamp_when_send_fails(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    _seed_email("g", urgency=9)
    monkeypatch.setattr(push, "_ingest_and_analyze", _async_noop)

    app = MagicMock()
    app.bot.send_message = AsyncMock(side_effect=RuntimeError("network"))

    sent = await push.tick(app, threshold=4)

    assert sent == 0
    # Critical: notified_at must NOT be set so the next tick retries.
    assert db.get_email_by_gmail_id("g")["notified_at"] is None


@pytest.mark.asyncio
async def test_tick_skips_when_chat_id_unset(monkeypatch):
    monkeypatch.delenv("TELEGRAM_AUTHORIZED_CHAT_ID", raising=False)
    _seed_email("g", urgency=9)
    monkeypatch.setattr(push, "_ingest_and_analyze", _async_noop)
    app = _stub_application()

    sent = await push.tick(app, threshold=4)
    assert sent == 0
    app.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_tick_calls_ingest_and_analyze(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    called = {"n": 0}

    async def fake_ingest():
        called["n"] += 1

    monkeypatch.setattr(push, "_ingest_and_analyze", fake_ingest)
    app = _stub_application()
    await push.tick(app, threshold=4)
    assert called["n"] == 1


@pytest.mark.asyncio
async def test_ingest_and_analyze_persists_and_analyzes(monkeypatch):
    monkeypatch.setattr(
        push,
        "gmail_fetch_recent",
        lambda **_: [
            {
                "id": "ig1",
                "thread_id": "t",
                "sender": "alice@example.com",
                "subject": "s",
                "body": "b",
                "snippet": "",
                "date": "",
            }
        ],
    )
    monkeypatch.setattr(
        push,
        "analyze_email",
        lambda email: {
            "summary": "ok",
            "category": "Work",
            "sentiment": "Casual",
            "action_required": "Reply",
            "urgency_score": 6,
        },
    )

    await push._ingest_and_analyze()

    row = db.get_email_by_gmail_id("ig1")
    assert row is not None
    assert row["urgency_score"] == 6


@pytest.mark.asyncio
async def test_ingest_and_analyze_swallows_gmail_failure(monkeypatch):
    """Gmail outage shouldn't crash the scheduler — log and move on."""

    def boom(**_):
        raise RuntimeError("gmail down")

    monkeypatch.setattr(push, "gmail_fetch_recent", boom)
    await push._ingest_and_analyze()  # must not raise


@pytest.mark.asyncio
async def test_ingest_and_analyze_logs_warning_on_transient_dns_error(monkeypatch, caplog):
    """socket.gaierror (subclass of OSError) → one-line warning, no traceback."""
    import socket

    def gai_fail(**_):
        raise socket.gaierror(11001, "getaddrinfo failed")

    monkeypatch.setattr(push, "gmail_fetch_recent", gai_fail)
    inserted: list = []
    monkeypatch.setattr(push.db, "insert_email", lambda e: inserted.append(e))

    with caplog.at_level("WARNING", logger="app.telegram.push"):
        await push._ingest_and_analyze()

    assert inserted == []  # nothing fetched → nothing inserted
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert any("transient" in r.getMessage().lower() for r in warnings)
    # Critical: no exception-level record (those carry full tracebacks).
    assert not any(r.exc_info for r in caplog.records if r.levelno >= 40)


@pytest.mark.asyncio
async def test_ingest_and_analyze_keeps_traceback_for_unexpected_errors(monkeypatch, caplog):
    """A non-network error (e.g. ValueError) must still surface a full traceback."""

    def boom(**_):
        raise ValueError("something else")

    monkeypatch.setattr(push, "gmail_fetch_recent", boom)
    with caplog.at_level("ERROR", logger="app.telegram.push"):
        await push._ingest_and_analyze()
    errors = [r for r in caplog.records if r.levelno >= 40]
    assert any(r.exc_info for r in errors), "unexpected error must log traceback"


@pytest.mark.asyncio
async def test_tick_does_not_block_event_loop(monkeypatch):
    """Concurrent task must make progress while a slow Gmail call is in-flight."""
    import time

    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")

    def slow_fetch(**_):
        time.sleep(0.5)  # synchronous block — must run in a worker thread
        return []

    monkeypatch.setattr(push, "gmail_fetch_recent", slow_fetch)
    app = _stub_application()

    parallel_done = asyncio.Event()

    async def parallel():
        await asyncio.sleep(0.1)
        parallel_done.set()

    parallel_task = asyncio.create_task(parallel())
    await push.tick(app, threshold=4)

    assert parallel_done.is_set(), "loop was blocked by sync gmail call"
    await parallel_task


def test_pause_and_resume_when_not_running():
    """pause/resume on a stopped scheduler is a no-op (no exceptions)."""
    assert push.pause() is False
    assert push.is_running() is False


def test_is_enabled_at_boot_defaults_to_true(monkeypatch):
    monkeypatch.delenv("TELEGRAM_PUSH_ENABLED", raising=False)
    assert push.is_enabled_at_boot() is True


@pytest.mark.parametrize("val", ["false", "0", "no", "OFF"])
def test_is_enabled_at_boot_false_values(monkeypatch, val):
    monkeypatch.setenv("TELEGRAM_PUSH_ENABLED", val)
    assert push.is_enabled_at_boot() is False


@pytest.mark.asyncio
async def test_start_stop_lifecycle():
    """start/stop should bring the scheduler up + down without raising."""
    app = _stub_application()
    push.start(app, interval_minutes=1, threshold=4)
    assert push.is_running() is True
    push.stop()
    assert push.is_running() is False


@pytest.mark.asyncio
async def test_pause_then_resume_round_trip():
    app = _stub_application()
    push.start(app, interval_minutes=1, threshold=4)
    assert push.pause() is True
    assert push.is_running() is False
    assert push.resume() is True
    assert push.is_running() is True
    push.stop()
