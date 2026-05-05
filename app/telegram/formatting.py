"""Telegram MarkdownV2 escaping + email/analysis renderers + 4096-char chunking."""

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


def _priority_emoji(urgency: int | None) -> str:
    """Map an urgency_score (1-10) to a colored circle. None / unknown → grey."""
    if urgency is None:
        return "⚪"
    if urgency >= 9:
        return "🔴"
    if urgency >= 5:
        return "🟡"
    return "🟢"


def format_unread_entry(email: dict, index: int) -> str:
    """Render one Gmail-fetched email as a numbered MarkdownV2 block."""
    sender = escape_markdown_v2(email.get("sender") or "Unknown sender")
    subject = escape_markdown_v2(email.get("subject") or "(no subject)")
    snippet = escape_markdown_v2(email.get("snippet") or "")
    return f"*{index}\\.* {sender}\n*Subject:* {subject}\n{snippet}"


def format_analysis_entry(email: dict, analysis: dict, index: int) -> str:
    """Render one email + Claude analysis result as a numbered MarkdownV2 block."""
    sender = escape_markdown_v2(email.get("sender") or "Unknown sender")
    subject = escape_markdown_v2(email.get("subject") or "(no subject)")
    category = escape_markdown_v2(analysis.get("category") or "Unknown")
    urgency = analysis.get("urgency_score")
    urgency_str = escape_markdown_v2(f"{urgency}/10" if urgency is not None else "n/a")
    summary = escape_markdown_v2(analysis.get("summary") or "")
    emoji = _priority_emoji(urgency)
    return (
        f"{emoji} *{index}\\.* {sender} — {subject}\n"
        f"*Category:* {category} \\| *Urgency:* {urgency_str}\n"
        f"{summary}"
    )


def format_inbox_entry(row: dict, index: int) -> str:
    """Render one analyzed-email DB row as a numbered MarkdownV2 block."""
    sender = escape_markdown_v2(row.get("sender") or "Unknown sender")
    subject = escape_markdown_v2(row.get("subject") or "(no subject)")
    summary = escape_markdown_v2(row.get("ai_summary") or "")
    emoji = _priority_emoji(row.get("urgency_score"))
    return f"{emoji} *{index}\\.* {sender} — {subject}\n{summary}"


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
