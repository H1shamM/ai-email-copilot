from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Query  # noqa: E402

from app.gmail.service import get_recent_emails  # noqa: E402
from app.ai.analyzer import analyze_email  # noqa: E402
from app.database import db  # noqa: E402

app = FastAPI(title="AI Email Copilot")


@app.on_event("startup")
def startup():
    db.init_db()


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
