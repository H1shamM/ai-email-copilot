"""Unit tests for the push scheduler — Telegram + Gmail + Claude all mocked."""

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

    monkeypatch.setattr(push, "_ingest_and_analyze", lambda: None)
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
    monkeypatch.setattr(push, "_ingest_and_analyze", lambda: None)
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
    monkeypatch.setattr(push, "_ingest_and_analyze", lambda: None)

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
    monkeypatch.setattr(push, "_ingest_and_analyze", lambda: None)
    app = _stub_application()

    sent = await push.tick(app, threshold=4)
    assert sent == 0
    app.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_tick_calls_ingest_and_analyze(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "42")
    called = {"n": 0}

    def fake_ingest():
        called["n"] += 1

    monkeypatch.setattr(push, "_ingest_and_analyze", fake_ingest)
    app = _stub_application()
    await push.tick(app, threshold=4)
    assert called["n"] == 1


def test_ingest_and_analyze_persists_and_analyzes(monkeypatch):
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

    push._ingest_and_analyze()

    row = db.get_email_by_gmail_id("ig1")
    assert row is not None
    assert row["urgency_score"] == 6


def test_ingest_and_analyze_swallows_gmail_failure(monkeypatch):
    """Gmail outage shouldn't crash the scheduler — log and move on."""

    def boom(**_):
        raise RuntimeError("gmail down")

    monkeypatch.setattr(push, "gmail_fetch_recent", boom)
    push._ingest_and_analyze()  # must not raise


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
