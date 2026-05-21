"""Agentic /agent flow: a Claude tool-use loop over the app's existing capabilities.

Read-only tools execute live so the model reasons over real inbox/calendar data;
mutating tools (send a reply, create a calendar event) are NEVER run inside the
loop — they're queued as pending actions for explicit user approval, preserving
the approve-before-act model already used by /reply and /schedule.
"""

import json
import os

from anthropic import Anthropic

from app.ai import MODEL
from app.ai.analyzer import analyze_email
from app.ai.reply_generator import regenerate_one
from app.calendar import scheduler
from app.calendar import service as calendar_service
from app.database import db
from app.gmail.service import send_reply as gmail_send_reply

_client: Anthropic | None = None

MAX_TOKENS = 1024
MAX_ITERATIONS = 5

SYSTEM_PROMPT = (
    "You are an email assistant agent operating over the user's Gmail and Google "
    "Calendar. Use the read-only tools to gather what you need, then propose any "
    "send-reply or create-event actions. Those actions require the user's approval "
    "and will not run until approved, so include the full reply body or event "
    "details when you call them. Reference emails by their numeric id. Be concise."
)

MUTATING_TOOLS = {"send_reply", "create_calendar_event"}


def _get_client() -> Anthropic:
    """Lazy Anthropic client so the API key is read after load_dotenv()."""
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


# --- Read-only tool implementations (safe to run automatically) ---------------


def _tool_list_recent_emails(limit: int = 10) -> list[dict]:
    """Return a compact list of recent emails for the model to reason over."""
    rows = db.get_recent_emails(limit=limit)
    return [
        {
            "id": r.get("id"),
            "sender": r.get("sender"),
            "subject": r.get("subject"),
            "snippet": r.get("snippet"),
            "category": r.get("category"),
            "urgency_score": r.get("urgency_score"),
        }
        for r in rows
    ]


def _tool_get_email(email_id: int) -> dict:
    """Return the full stored email row, or an error marker if it's missing."""
    email = db.get_email_by_row_id(email_id)
    return email or {"error": f"no email with id {email_id}"}


def _tool_analyze_email(email_id: int) -> dict:
    """Run Claude analysis on a stored email and return the structured result."""
    email = db.get_email_by_row_id(email_id)
    if not email:
        return {"error": f"no email with id {email_id}"}
    return analyze_email(email) or {"error": "analysis failed"}


def _tool_check_calendar_availability(start_iso: str, end_iso: str) -> dict:
    """Return busy intervals in the window and whether it's free."""
    busy = calendar_service.check_busy(start_iso, end_iso)
    return {"busy": busy, "free": not busy}


def _tool_draft_reply(email_id: int, tone: str = "professional") -> dict:
    """Generate a single reply draft so the model can propose sending it."""
    email = db.get_email_by_row_id(email_id)
    if not email:
        return {"error": f"no email with id {email_id}"}
    text = regenerate_one(email, tone)
    if not text:
        return {"error": "draft generation failed"}
    return {"tone": tone, "text": text}


_READ_ONLY_DISPATCH = {
    "list_recent_emails": _tool_list_recent_emails,
    "get_email": _tool_get_email,
    "analyze_email": _tool_analyze_email,
    "check_calendar_availability": _tool_check_calendar_availability,
    "draft_reply": _tool_draft_reply,
}


TOOLS = [
    {
        "name": "list_recent_emails",
        "description": "List recent emails (id, sender, subject, snippet, category, urgency).",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "How many emails (default 10)."}
            },
        },
    },
    {
        "name": "get_email",
        "description": "Get the full stored email by its numeric id.",
        "input_schema": {
            "type": "object",
            "properties": {"email_id": {"type": "integer"}},
            "required": ["email_id"],
        },
    },
    {
        "name": "analyze_email",
        "description": "Run AI analysis (summary, category, urgency, action) on an email by id.",
        "input_schema": {
            "type": "object",
            "properties": {"email_id": {"type": "integer"}},
            "required": ["email_id"],
        },
    },
    {
        "name": "check_calendar_availability",
        "description": "Check busy/free for a time window. Times are RFC3339 UTC (…Z).",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_iso": {"type": "string"},
                "end_iso": {"type": "string"},
            },
            "required": ["start_iso", "end_iso"],
        },
    },
    {
        "name": "draft_reply",
        "description": "Generate a reply draft for an email so you can propose sending it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email_id": {"type": "integer"},
                "tone": {
                    "type": "string",
                    "description": "professional | friendly | brief (default professional).",
                },
            },
            "required": ["email_id"],
        },
    },
    {
        "name": "send_reply",
        "description": (
            "Propose sending a reply to an email. Requires user approval before it runs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email_id": {"type": "integer"},
                "body": {"type": "string", "description": "The full reply text to send."},
            },
            "required": ["email_id", "body"],
        },
    },
    {
        "name": "create_calendar_event",
        "description": (
            "Propose creating a calendar event. Requires user approval. "
            "start_iso is RFC3339 UTC (…Z)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start_iso": {"type": "string"},
                "duration_minutes": {"type": "integer", "description": "Default 30."},
                "location": {"type": "string"},
                "participants": {"type": "string", "description": "Comma-separated emails."},
            },
            "required": ["title", "start_iso"],
        },
    },
]


def _collect_text(content: list) -> str:
    """Join the text blocks of a response's content list."""
    parts = []
    for block in content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()


def _handle_tool_use(block, pending: list[dict]) -> str:
    """Execute a read-only tool, or queue a mutating one; return the tool_result text."""
    name = getattr(block, "name", "")
    args = getattr(block, "input", None) or {}
    if name in MUTATING_TOOLS:
        pending.append({"name": name, "input": args})
        return "PENDING_APPROVAL: queued for user approval."
    fn = _READ_ONLY_DISPATCH.get(name)
    if fn is None:
        return f"ERROR: unknown tool {name!r}"
    try:
        return json.dumps(fn(**args), default=str)
    except Exception as exc:  # noqa: BLE001 — feed the error back to the model, don't crash
        return f"ERROR: tool {name} failed: {exc}"


def run_agent(instruction: str) -> tuple[str, list[dict]]:
    """Run the tool-use loop for one instruction.

    Returns (final_text, pending_actions). pending_actions is the ordered list of
    mutating tool calls the model proposed but that were NOT executed — the caller
    must get user approval and pass each to execute_action.
    """
    client = _get_client()
    messages: list[dict] = [{"role": "user", "content": instruction}]
    pending: list[dict] = []
    final_text = ""

    for _ in range(MAX_ITERATIONS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        text = _collect_text(response.content)
        if text:
            final_text = text

        if getattr(response, "stop_reason", None) != "tool_use":
            break

        messages.append({"role": "assistant", "content": response.content})
        tool_results = [
            {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": _handle_tool_use(block, pending),
            }
            for block in response.content
            if getattr(block, "type", None) == "tool_use"
        ]
        messages.append({"role": "user", "content": tool_results})

    return final_text.strip(), pending


# --- Mutating action execution (run only after user approval) ------------------


def describe_action(action: dict) -> str:
    """One-line human summary of a queued action for the approval prompt."""
    name = action.get("name")
    args = action.get("input") or {}
    if name == "send_reply":
        preview = (args.get("body") or "").replace("\n", " ")
        if len(preview) > 120:
            preview = preview[:117] + "…"
        return f"Send reply to email {args.get('email_id')}: {preview}"
    if name == "create_calendar_event":
        return (
            f"Create event '{args.get('title')}' at {args.get('start_iso')} "
            f"({args.get('duration_minutes') or 30} min)"
        )
    return f"{name} {args}"


def execute_action(action: dict) -> str:
    """Run a single approved mutating action; return a human-readable result."""
    name = action.get("name")
    args = action.get("input") or {}
    if name == "send_reply":
        return _exec_send_reply(**args)
    if name == "create_calendar_event":
        return _exec_create_calendar_event(**args)
    return f"Unknown action {name!r}"


def _exec_send_reply(email_id: int, body: str) -> str:
    """Send a reply to a stored email via Gmail."""
    email = db.get_email_by_row_id(email_id)
    if not email:
        return f"Email {email_id} not found."
    gmail_send_reply(email["thread_id"], email["gmail_message_id"], body)
    return f"Reply sent to email {email_id}."


def _exec_create_calendar_event(
    title: str,
    start_iso: str,
    duration_minutes: int | None = None,
    location: str | None = None,
    participants: str | None = None,
) -> str:
    """Create a Google Calendar event from agent-supplied fields."""
    event_date, event_time = _split_iso(start_iso)
    event_row = {
        "title": title,
        "event_date": event_date,
        "event_time": event_time,
        "duration_minutes": duration_minutes,
        "location": location,
        "participants": participants,
    }
    google_event_id = scheduler.create_event(event_row)
    return f"Calendar event created: {title} ({google_event_id})."


def _split_iso(iso: str) -> tuple[str | None, str | None]:
    """Split an RFC3339/ISO datetime into (date, time) parts for scheduler.create_event."""
    cleaned = (iso or "").replace("Z", "").strip()
    if "T" not in cleaned:
        return (cleaned or None), None
    date_part, _, time_part = cleaned.partition("T")
    return (date_part or None), (time_part or None)
