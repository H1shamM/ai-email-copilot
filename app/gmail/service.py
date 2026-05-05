import base64
from email.mime.text import MIMEText

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


REPLY_HEADERS = ["From", "To", "Subject", "Message-ID", "References", "Reply-To"]


def build_reply_mime(
    to: str,
    subject: str,
    body: str,
    in_reply_to: str | None,
    references: str | None,
) -> bytes:
    """Build a base MIME reply with threading headers.

    `in_reply_to` is the RFC 822 Message-ID of the email being replied to (NOT
    the Gmail message id). `references` is the original References header, if
    any — appended to so the new message points back through the chain.
    """
    msg = MIMEText(body, _charset="utf-8")
    msg["To"] = to
    msg["Subject"] = subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        chain = f"{references} {in_reply_to}".strip() if references else in_reply_to
        msg["References"] = chain
    return msg.as_bytes()


def make_reply_envelope(original_headers: list, thread_id: str, body: str) -> dict:
    """Compose the {raw, threadId} envelope Gmail.send expects.

    Pure function so it can be unit-tested without a Gmail service object.
    """
    rfc_message_id = _get_header(original_headers, "Message-ID")
    references = _get_header(original_headers, "References")
    to_addr = _get_header(original_headers, "Reply-To") or _get_header(original_headers, "From")
    subject = _get_header(original_headers, "Subject") or ""
    if subject and not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    if not to_addr:
        raise ValueError("Original message has no From/Reply-To header — cannot reply")

    mime_bytes = build_reply_mime(
        to=to_addr,
        subject=subject,
        body=body,
        in_reply_to=rfc_message_id,
        references=references,
    )
    raw = base64.urlsafe_b64encode(mime_bytes).decode("ascii")
    return {"raw": raw, "threadId": thread_id}


def send_reply(thread_id: str, message_id: str, body: str) -> str:  # pragma: no cover
    """Send a reply that threads under the original message; returns new Gmail id."""
    service = get_email_service()
    original = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="metadata", metadataHeaders=REPLY_HEADERS)
        .execute()
    )
    envelope = make_reply_envelope(
        original.get("payload", {}).get("headers", []),
        thread_id,
        body,
    )
    sent = service.users().messages().send(userId="me", body=envelope).execute()
    return sent["id"]


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
