import base64
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.gmail.auth import get_credentials


def get_email_service():  # pragma: no cover
    credentials = get_credentials()
    service = build("gmail", "v1", credentials=credentials)
    return service


def _get_header(headers, name):
    for header in headers:
        if header["name"].lower() == name.lower():
            return header["value"]
    return None


def _get_body(payload):
    """Extract plain text body from email payload."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    parts = payload.get("parts", [])
    for part in parts:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        # Check nested parts (e.g. multipart/alternative inside multipart/mixed)
        nested = part.get("parts", [])
        for nested_part in nested:
            if nested_part.get("mimeType") == "text/plain" and nested_part.get("body", {}).get(
                "data"
            ):
                return base64.urlsafe_b64decode(nested_part["body"]["data"]).decode(
                    "utf-8", errors="replace"
                )

    return None


def parse_email(msg_data):
    """Parse raw Gmail API message into structured dict."""
    headers = msg_data.get("payload", {}).get("headers", [])
    payload = msg_data.get("payload", {})

    return {
        "id": msg_data.get("id"),
        "thread_id": msg_data.get("threadId"),
        "sender": _get_header(headers, "From"),
        "subject": _get_header(headers, "Subject"),
        "date": _get_header(headers, "Date"),
        "snippet": msg_data.get("snippet", ""),
        "body": _get_body(payload),
    }


def get_recent_emails(max_results=50, unread_only=True):  # pragma: no cover
    """Fetch recent emails with full metadata.

    Args:
        max_results: Maximum number of emails to fetch.
        unread_only: If True, only fetch unread emails.
    """
    service = get_email_service()

    query = "is:unread" if unread_only else None

    try:
        results = (
            service.users().messages().list(userId="me", maxResults=max_results, q=query).execute()
        )
    except HttpError as error:
        raise RuntimeError(f"Failed to list emails: {error}")

    messages = results.get("messages", [])
    emails = []

    for message in messages:
        try:
            msg_data = (
                service.users()
                .messages()
                .get(userId="me", id=message["id"], format="full")
                .execute()
            )
            emails.append(parse_email(msg_data))
        except HttpError:
            # Skip individual message failures
            continue

    return emails
