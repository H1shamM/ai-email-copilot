"""Tests for the POST /telegram/webhook route in app/main.py."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _payload() -> dict:
    return {"update_id": 1, "message": {"message_id": 1, "text": "/start"}}


def test_webhook_rejects_missing_secret(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "expected")
    response = client.post("/telegram/webhook", json=_payload())
    assert response.status_code == 403


def test_webhook_rejects_wrong_secret(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "expected")
    response = client.post(
        "/telegram/webhook",
        json=_payload(),
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert response.status_code == 403


def test_webhook_dispatches_when_secret_matches(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "expected")
    with patch(
        "app.main.telegram_bot.process_update_from_json",
        new=AsyncMock(return_value=None),
    ) as process_mock:
        response = client.post(
            "/telegram/webhook",
            json=_payload(),
            headers={"X-Telegram-Bot-Api-Secret-Token": "expected"},
        )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    process_mock.assert_awaited_once_with(_payload())


def test_webhook_skips_secret_check_when_unset(monkeypatch):
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    with patch(
        "app.main.telegram_bot.process_update_from_json",
        new=AsyncMock(return_value=None),
    ) as process_mock:
        response = client.post("/telegram/webhook", json=_payload())
    assert response.status_code == 200
    process_mock.assert_awaited_once()
