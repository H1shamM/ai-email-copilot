import logging
import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Header, HTTPException, Query, Request  # noqa: E402

from app.gmail.service import get_recent_emails  # noqa: E402
from app.ai.analyzer import analyze_email  # noqa: E402
from app.database import db  # noqa: E402
from app.telegram import bot as telegram_bot  # noqa: E402
from app.telegram import push as telegram_push  # noqa: E402

logger = logging.getLogger(__name__)

app = FastAPI(title="AI Email Copilot")


@app.on_event("startup")
async def startup():
    db.init_db()

    webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")
    secret_token = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if not webhook_url:
        logger.warning("TELEGRAM_WEBHOOK_URL not set; skipping Telegram webhook registration")
        return

    await telegram_bot.initialize()
    application = telegram_bot.get_application()
    await application.bot.set_webhook(url=webhook_url, secret_token=secret_token)
    logger.info("Telegram webhook registered at %s", webhook_url)

    if telegram_push.is_enabled_at_boot():
        interval = int(os.getenv("TELEGRAM_PUSH_INTERVAL_MINUTES", "5"))
        threshold = int(os.getenv("TELEGRAM_PUSH_THRESHOLD", "4"))
        telegram_push.start(application, interval_minutes=interval, threshold=threshold)


@app.on_event("shutdown")
async def shutdown():
    telegram_push.stop()
    await telegram_bot.shutdown()


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    """Receive updates from Telegram and dispatch through the bot Application."""
    expected_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if expected_secret and x_telegram_bot_api_secret_token != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    payload = await request.json()
    await telegram_bot.process_update_from_json(payload)
    return {"ok": True}


@app.get("/")
def root():
    return {"message": "AI Email Copilot running"}


@app.get("/emails")
def get_emails(
    max_results: int = Query(default=50, le=100),
    unread_only: bool = Query(default=True),
):
    try:
        emails = get_recent_emails(max_results=max_results, unread_only=unread_only)
        return {"count": len(emails), "emails": emails}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/emails/fetch")
def fetch_and_store_emails(
    max_results: int = Query(default=50, le=100),
    unread_only: bool = Query(default=True),
):
    """Fetch emails from Gmail and store them in the database."""
    try:
        emails = get_recent_emails(max_results=max_results, unread_only=unread_only)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    stored = 0
    for email_data in emails:
        row_id = db.insert_email(email_data)
        if row_id:
            stored += 1

    return {"fetched": len(emails), "stored": stored}


@app.post("/emails/analyze")
def analyze_stored_emails():
    """Analyze all unprocessed emails with Claude AI."""
    unprocessed = db.get_unprocessed_emails()
    if not unprocessed:
        return {"message": "No unprocessed emails found", "analyzed": 0}

    results = []
    for email in unprocessed:
        analysis = analyze_email(email)
        if analysis:
            db.update_analysis(email["gmail_message_id"], analysis)
            results.append(
                {
                    "gmail_message_id": email["gmail_message_id"],
                    "subject": email["subject"],
                    "analysis": analysis,
                }
            )

    return {"analyzed": len(results), "results": results}


@app.get("/emails/analyzed")
def get_analyzed_emails(limit: int = Query(default=50, le=100)):
    """Get emails with their AI analysis from the database."""
    return {"emails": db.get_recent_emails(limit=limit)}
