"""Telegram MarkdownV2 escaping + email/analysis renderers + 4096-char chunking."""

import re
from datetime import datetime
from email.utils import parseaddr

from dateutil import parser as date_parser

# Per https://core.telegram.org/bots/api#markdownv2-style — these MUST be escaped
# anywhere they appear in user-supplied text, otherwise the bot API returns
# "Bad Request: can't parse entities".
_MD_V2_RESERVED = r"_*[]()~`>#+-=|{}.!\\"
_MD_V2_TRANSLATION = str.maketrans({c: f"\\{c}" for c in _MD_V2_RESERVED})

TELEGRAM_MAX_MESSAGE_LEN = 4096


def escape_markdown_v2(text: str | None) -> str:
    """Escape all Telegram MarkdownV2 reserved characters in a single pass."""
    if not text:
        return ""
    return text.translate(_MD_V2_TRANSLATION)


_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_HEADER_RE = re.compile(r"^\s*#{1,6}\s+(.*)$")
_BULLET_RE = re.compile(r"^(\s*)[-*]\s+(.*)$")


def _md2_inline(text: str) -> str:
    """Escape a single line for MarkdownV2, rendering **bold** as *bold*."""
    parts: list[str] = []
    last = 0
    for m in _BOLD_RE.finditer(text):
        parts.append(escape_markdown_v2(text[last : m.start()]))
        parts.append("*" + escape_markdown_v2(m.group(1)) + "*")
        last = m.end()
    parts.append(escape_markdown_v2(text[last:]))
    return "".join(parts)


def agent_text_to_md2(text: str | None) -> str:
    """Convert the agent's standard-Markdown reply to Telegram MarkdownV2.

    `## headers` and `**bold**` become bold, `-`/`*` bullets become `•`, and
    everything else is escaped. Caller should fall back to `strip_markdown` on a
    MarkdownV2 send error.
    """
    out: list[str] = []
    for line in (text or "").split("\n"):
        header = _HEADER_RE.match(line)
        if header:
            out.append("*" + _md2_inline(header.group(1)) + "*")
            continue
        bullet = _BULLET_RE.match(line)
        if bullet:
            out.append(f"{bullet.group(1)}• {_md2_inline(bullet.group(2))}")
            continue
        out.append(_md2_inline(line))
    return "\n".join(out)


def strip_markdown(text: str | None) -> str:
    """Strip Markdown to clean plain text (the no-parse-mode fallback)."""
    out: list[str] = []
    for line in (text or "").split("\n"):
        line = re.sub(r"^\s*#{1,6}\s+", "", line)
        line = _BOLD_RE.sub(r"\1", line)
        line = re.sub(r"^(\s*)[-*]\s+", r"\1• ", line)
        out.append(line)
    return "\n".join(out)


def _priority_emoji(urgency: int | None) -> str:
    """Map an urgency_score (1-10) to a colored circle. None / unknown → grey."""
    if urgency is None:
        return "⚪"
    if urgency >= 9:
        return "🔴"
    if urgency >= 5:
        return "🟡"
    return "🟢"


# ccTLD second-level domains where the org label is the third-from-last part.
_MULTI_PART_TLDS = {"co.uk", "co.il", "com.au", "co.jp", "org.uk", "co.nz", "com.br"}


def _sender_org(addr: str) -> str:
    """The org label of an email's domain (e.g. swiftness@…co.il → 'swiftness').

    Avoids showing a full address, which Telegram auto-links into blue noise.
    """
    domain = addr.rsplit("@", 1)[-1].lower()
    labels = domain.split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in _MULTI_PART_TLDS:
        return labels[-3]
    if len(labels) >= 2:
        return labels[-2]
    return domain or addr


def sender_display_name(raw_sender: str | None) -> str:
    """The human-friendly sender: display name when present, else the domain org.

    Drops the `Name <addr>` duplication and avoids a bare address that Telegram
    would auto-link.
    """
    name, addr = parseaddr(raw_sender or "")
    if name:
        return name
    if addr and "@" in addr:
        return _sender_org(addr)
    return addr or (raw_sender or "Unknown sender")


def _truncate(text: str, limit: int) -> str:
    """Trim to `limit` chars with an ellipsis so list rows stay one line each."""
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


_ACTION_GLYPH = {
    "Reply": "✍️",
    "Schedule": "📅",
    "Read": "📖",
    "Archive": "🗄",
    "Flag": "🚩",
}


def _action_glyph(action: str | None) -> str:
    """Glyph for an analyzer action_required; empty string when unknown."""
    return _ACTION_GLYPH.get(action or "", "")


def _short_time(date_str: str | None, now: datetime | None = None, full: bool = False) -> str:
    """Parse a received/created timestamp into a short label; '' if unparseable.

    Today → `HH:MM`, otherwise `DD Mon`. `full` gives `DD Mon YYYY, HH:MM` for the
    detail view. Naive comparison (tz dropped) — good enough for a recency hint.
    """
    if not date_str:
        return ""
    try:
        dt = date_parser.parse(date_str).replace(tzinfo=None)
    except (ValueError, OverflowError, TypeError):
        return ""
    if full:
        return dt.strftime("%d %b %Y, %H:%M")
    now = now or datetime.now()
    return dt.strftime("%H:%M") if dt.date() == now.date() else dt.strftime("%d %b")


_SUBJECT_LIMIT = 70
_PREVIEW_LIMIT = 110


def format_unread_entry(email: dict, index: int) -> str:
    """Render one Gmail-fetched email as a compact numbered MarkdownV2 card."""
    name = escape_markdown_v2(sender_display_name(email.get("sender")))
    subject = escape_markdown_v2(_truncate(email.get("subject") or "(no subject)", _SUBJECT_LIMIT))
    snippet = escape_markdown_v2(_truncate(email.get("snippet") or "", _PREVIEW_LIMIT))
    lines = [f"*{index}\\.* *{name}*", f"✉️ {subject}"]
    if snippet:
        lines.append(f"   ↳ {snippet}")
    return "\n".join(lines)


def _id_prefix(row: dict) -> str:
    """Render `*#<id>*` (MarkdownV2-escaped) so /reply <id> mirrors what's on screen."""
    row_id = row.get("id")
    if row_id is None:
        return "*\\#?*"
    return f"*\\#{row_id}*"


def format_analysis_entry(email: dict, analysis: dict) -> str:
    """Render one email + Claude analysis result as a MarkdownV2 block keyed by row id."""
    sender = escape_markdown_v2(email.get("sender") or "Unknown sender")
    subject = escape_markdown_v2(email.get("subject") or "(no subject)")
    category = escape_markdown_v2(analysis.get("category") or "Unknown")
    urgency = analysis.get("urgency_score")
    urgency_str = escape_markdown_v2(f"{urgency}/10" if urgency is not None else "n/a")
    summary = escape_markdown_v2(analysis.get("summary") or "")
    emoji = _priority_emoji(urgency)
    return (
        f"{emoji} {_id_prefix(email)} {sender} — {subject}\n"
        f"*Category:* {category} \\| *Urgency:* {urgency_str}\n"
        f"{summary}"
    )


def format_inbox_entry(row: dict) -> str:
    """Render one analyzed-email DB row as a compact MarkdownV2 card keyed by row id.

    Line 1 carries the decision signals: priority, id, sender, a recency hint, and
    the suggested-action glyph. Lines 2-3 are subject + a one-line summary.
    """
    name = escape_markdown_v2(sender_display_name(row.get("sender")))
    subject = escape_markdown_v2(_truncate(row.get("subject") or "(no subject)", _SUBJECT_LIMIT))
    summary = escape_markdown_v2(_truncate(row.get("ai_summary") or "", _PREVIEW_LIMIT))
    emoji = _priority_emoji(row.get("urgency_score"))

    header = f"{emoji} {_id_prefix(row)} · *{name}*"
    when = _short_time(row.get("received_date") or row.get("created_at"))
    if when:
        header += f" · {escape_markdown_v2(when)}"
    glyph = _action_glyph(row.get("action_required"))
    if glyph:
        header += f" · {glyph}"

    lines = [header, f"✉️ {subject}"]
    if summary:
        lines.append(f"   ↳ {summary}")
    return "\n".join(lines)


def format_email_detail(row: dict) -> str:
    """Render the full single-email detail view (untruncated) for `/email <id>`."""
    emoji = _priority_emoji(row.get("urgency_score"))
    urgency = row.get("urgency_score")
    urgency_str = escape_markdown_v2(f"{urgency}/10" if urgency is not None else "n/a")
    sender = escape_markdown_v2(row.get("sender") or "Unknown sender")
    when = escape_markdown_v2(
        _short_time(row.get("received_date") or row.get("created_at"), full=True)
    )
    category = escape_markdown_v2(row.get("category") or "Unknown")
    action = row.get("action_required")
    subject = escape_markdown_v2(row.get("subject") or "(no subject)")
    summary = escape_markdown_v2(row.get("ai_summary") or "(not analyzed yet — run /analyze)")

    meta = f"📂 {category}"
    if when:
        meta = f"🕑 {when}   {meta}"
    glyph = _action_glyph(action)
    if action:
        meta += f"   {glyph} {escape_markdown_v2(action)}"

    return (
        f"{emoji} {_id_prefix(row)} · *urgency {urgency_str}*\n\n"
        f"👤 {sender}\n"
        f"{meta}\n\n"
        f"✉️ *{subject}*\n\n"
        f"📝 {summary}"
    )


_TONE_LABEL = {
    "professional": "🎩 Professional",
    "friendly": "😊 Friendly",
    "brief": "⚡ Brief",
}


def format_drafts_message(email: dict, drafts: list[dict]) -> str:
    """Render an email + 3 tone drafts as a single MarkdownV2 message.

    `drafts` is a list of draft_replies rows (must have `tone` and `draft_text`).
    """
    sender = escape_markdown_v2(email.get("sender") or "Unknown sender")
    subject = escape_markdown_v2(email.get("subject") or "(no subject)")
    header = f"📧 *Drafts for:* {sender}\n*Subject:* {subject}"

    by_tone = {d["tone"]: d for d in drafts}
    sections: list[str] = [header]
    for tone in ("professional", "friendly", "brief"):
        draft = by_tone.get(tone)
        if not draft:
            continue
        label = _TONE_LABEL.get(tone, tone.title())
        body = escape_markdown_v2(draft.get("draft_text") or "")
        sections.append(f"\n*{escape_markdown_v2(label)}*\n{body}")
    return "".join(sections) if len(sections) == 1 else "\n".join(sections)


def format_single_draft(email: dict, draft_text: str) -> str:
    """Render one draft (in the user's voice) as a MarkdownV2 message."""
    sender = escape_markdown_v2(sender_display_name(email.get("sender")))
    subject = escape_markdown_v2(email.get("subject") or "(no subject)")
    body = escape_markdown_v2(draft_text or "")
    return f"✍️ *Draft reply to* {sender}\n*Re:* {subject}\n\n{body}"


def format_notification(row: dict) -> str:
    """MarkdownV2 push-notification block: sender, subject, category, urgency, summary."""
    sender = escape_markdown_v2(row.get("sender") or "Unknown sender")
    subject = escape_markdown_v2(row.get("subject") or "(no subject)")
    category = escape_markdown_v2(row.get("category") or "Unknown")
    urgency = row.get("urgency_score")
    urgency_str = escape_markdown_v2(f"{urgency}/10" if urgency is not None else "n/a")
    summary = escape_markdown_v2(row.get("ai_summary") or "")
    emoji = _priority_emoji(urgency)
    return (
        f"{emoji} *Priority email*\n"
        f"*From:* {sender}\n"
        f"*Subject:* {subject}\n"
        f"*Category:* {category} \\| *Urgency:* {urgency_str}\n"
        f"{summary}"
    )


def chunk_messages(blocks: list[str], max_len: int = TELEGRAM_MAX_MESSAGE_LEN) -> list[str]:
    """Pack blocks into messages of at most max_len characters.

    Blocks are joined with a blank line. A single oversized block is sent as
    its own message rather than being split mid-record (per Story B AC).
    """
    if not blocks:
        return []
    separator = "\n\n"
    messages: list[str] = []
    current: list[str] = []
    current_len = 0
    for block in blocks:
        addition = len(block) if not current else len(separator) + len(block)
        if current and current_len + addition > max_len:
            messages.append(separator.join(current))
            current = [block]
            current_len = len(block)
        else:
            current.append(block)
            current_len += addition
    if current:
        messages.append(separator.join(current))
    return messages
