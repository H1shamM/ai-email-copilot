"""Tests for app/telegram/formatting.py — escaping, renderers, chunking."""

from datetime import datetime

from app.telegram.formatting import (
    agent_text_to_md2,
    chunk_messages,
    escape_markdown_v2,
    format_analysis_entry,
    format_email_detail,
    format_inbox_entry,
    format_notification,
    format_unread_entry,
    sender_display_name,
    strip_markdown,
)
from app.telegram import formatting


def test_agent_text_to_md2_renders_bold_and_headers():
    md2 = agent_text_to_md2("## Urgent\nStart with **the deploy failures** now.")
    assert md2.startswith("*Urgent*")  # header -> bold
    assert "*the deploy failures*" in md2  # **bold** -> *bold*
    assert "**" not in md2 and "##" not in md2  # no literal markdown left


def test_agent_text_to_md2_escapes_reserved_chars():
    # A bare '.' and '(' must be escaped so MarkdownV2 doesn't choke.
    md2 = agent_text_to_md2("Reply to priya@x.com (urgent).")
    assert "priya@x\\.com" in md2
    assert "\\(urgent\\)" in md2


def test_agent_text_to_md2_converts_bullets():
    assert "• item" in agent_text_to_md2("- item")


def test_strip_markdown_removes_syntax():
    plain = strip_markdown("## Head\n**bold** text\n- item")
    assert plain == "Head\nbold text\n• item"


def test_short_time_today_shows_clock(monkeypatch):
    now = datetime(2026, 5, 10, 18, 0, 0)
    assert formatting._short_time("Sun, 10 May 2026 09:30:00 +0000", now=now) == "09:30"


def test_short_time_other_day_shows_date(monkeypatch):
    now = datetime(2026, 5, 12, 0, 0, 0)
    assert formatting._short_time("Sun, 10 May 2026 09:30:00 +0000", now=now) == "10 May"


def test_short_time_unparseable_returns_empty():
    assert formatting._short_time("not a date") == ""
    assert formatting._short_time(None) == ""


def test_format_inbox_entry_shows_action_glyph():
    row = {"id": 1, "sender": "A", "subject": "s", "ai_summary": "x", "action_required": "Schedule"}
    assert "📅" in format_inbox_entry(row)


def test_format_email_detail_has_full_fields_and_no_truncation():
    row = {
        "id": 9,
        "sender": "Boss <boss@corp.com>",
        "subject": "Q3 plan",
        "ai_summary": "y" * 200,
        "urgency_score": 9,
        "category": "Work",
        "action_required": "Reply",
        "received_date": "Mon, 10 May 2026 09:00:00 +0000",
    }
    block = format_email_detail(row)
    assert "*\\#9*" in block
    assert "boss@corp\\.com" in block  # full address kept in detail
    assert "Work" in block
    assert "y" * 200 in block  # summary NOT truncated in the detail view
    assert "…" not in block
    assert "✉️ *Q3 plan*" in block


def test_sender_display_name_prefers_display_name():
    assert sender_display_name("Qodo <no-reply@qodo.com>") == "Qodo"


def test_sender_display_name_uses_domain_org_when_no_name():
    # No display name → show the org label, not an auto-linkable bare address.
    assert sender_display_name("no-reply@qodo.com") == "qodo"
    assert sender_display_name("doNotReply@swiftness.co.il") == "swiftness"


def test_sender_display_name_handles_none():
    assert sender_display_name(None) == "Unknown sender"


def test_format_inbox_entry_drops_raw_address_and_truncates_long_summary():
    row = {
        "id": 3,
        "sender": "Qodo <no-reply@qodo.com>",
        "subject": "Thank you",
        "ai_summary": "x" * 200,
        "urgency_score": 5,
    }
    block = format_inbox_entry(row)
    assert "*Qodo*" in block
    assert "no-reply@qodo" not in block  # raw address gone
    assert "✉️ Thank you" in block
    assert "…" in block  # long summary truncated
    assert "↳" in block


def test_escape_markdown_v2_passes_plain_text_through():
    assert escape_markdown_v2("hello world") == "hello world"


def test_escape_markdown_v2_returns_empty_for_none():
    assert escape_markdown_v2(None) == ""


def test_escape_markdown_v2_returns_empty_for_empty_string():
    assert escape_markdown_v2("") == ""


def test_escape_markdown_v2_escapes_all_reserved_chars():
    reserved = r"_*[]()~`>#+-=|{}.!\\"
    escaped = escape_markdown_v2(reserved)
    for char in reserved:
        assert f"\\{char}" in escaped


def test_escape_markdown_v2_escapes_email_address_dot():
    assert escape_markdown_v2("alice@example.com") == "alice@example\\.com"


def test_format_unread_entry_happy_path():
    email = {
        "sender": "Alice <alice@example.com>",
        "subject": "Hi",
        "snippet": "Just checking in",
    }
    block = format_unread_entry(email, 1)
    assert "*1\\.*" in block
    assert "*Alice*" in block  # display name, not the raw <addr>
    assert "alice@example" not in block  # raw address dropped
    assert "✉️ Hi" in block
    assert "Just checking in" in block


def test_format_unread_entry_handles_missing_fields():
    block = format_unread_entry({}, 2)
    assert "*2\\.*" in block
    assert "Unknown sender" in block
    assert "\\(no subject\\)" in block


def test_format_analysis_entry_high_urgency_gets_red():
    email = {"id": 5, "sender": "boss@corp.com", "subject": "URGENT"}
    analysis = {"category": "Work", "urgency_score": 10, "summary": "Reply ASAP"}
    block = format_analysis_entry(email, analysis)
    assert block.startswith("🔴")
    assert "*\\#5*" in block  # row id is what /reply takes
    assert "*Category:* Work" in block
    assert "10/10" in block
    assert "Reply ASAP" in block


def test_format_analysis_entry_medium_urgency_gets_yellow():
    block = format_analysis_entry({"id": 1, "sender": "x"}, {"urgency_score": 6})
    assert block.startswith("🟡")


def test_format_analysis_entry_low_urgency_gets_green():
    block = format_analysis_entry({"id": 1, "sender": "x"}, {"urgency_score": 2})
    assert block.startswith("🟢")


def test_format_analysis_entry_missing_urgency_shows_na():
    block = format_analysis_entry({"id": 1, "sender": "x"}, {"category": "Other"})
    assert block.startswith("⚪")
    assert "n/a" in block


def test_format_analysis_entry_missing_id_falls_back():
    """Defensive: dict without id should render '#?' rather than crash."""
    block = format_analysis_entry({"sender": "x"}, {"urgency_score": 3})
    assert "*\\#?*" in block


def test_format_inbox_entry_happy_path():
    row = {
        "id": 12,
        "sender": "alice@example.com",
        "subject": "Update",
        "ai_summary": "All good.",
        "urgency_score": 9,
    }
    block = format_inbox_entry(row)
    assert block.startswith("🔴")
    assert "*\\#12*" in block
    assert "example" in block  # nameless sender → domain org label, not bare address
    assert "Update" in block
    assert "All good\\." in block


def test_format_inbox_entry_handles_missing_analysis():
    block = format_inbox_entry({"id": 7, "sender": "x", "subject": "y"})
    assert block.startswith("⚪")


def test_chunk_messages_empty_list_returns_empty():
    assert chunk_messages([]) == []


def test_chunk_messages_single_block_fits_in_one_message():
    assert chunk_messages(["hello"]) == ["hello"]


def test_chunk_messages_joins_blocks_under_limit_with_blank_line():
    result = chunk_messages(["a", "b", "c"])
    assert result == ["a\n\nb\n\nc"]


def test_chunk_messages_splits_when_total_exceeds_limit():
    blocks = ["x" * 100, "y" * 100, "z" * 100]
    result = chunk_messages(blocks, max_len=210)
    assert len(result) == 2
    assert result[0] == "x" * 100 + "\n\n" + "y" * 100
    assert result[1] == "z" * 100


def test_chunk_messages_oversized_single_block_gets_own_message():
    blocks = ["short", "x" * 200, "another short"]
    result = chunk_messages(blocks, max_len=50)
    assert "short" in result[0]
    assert "x" * 200 in result[1]
    assert "another short" in result[2]


def test_chunk_messages_never_splits_mid_block():
    big_block = "y" * 5000
    result = chunk_messages([big_block], max_len=4096)
    assert result == [big_block]


def test_format_notification_includes_all_fields():
    row = {
        "sender": "alice@example.com",
        "subject": "Server down!",
        "category": "Work",
        "urgency_score": 9,
        "ai_summary": "Production database is unreachable.",
    }
    out = format_notification(row)
    assert "🔴" in out
    assert "Priority email" in out
    assert "alice@example\\.com" in out
    assert "Server down\\!" in out
    assert "Work" in out
    assert "9/10" in out
    assert "Production database is unreachable\\." in out


def test_format_notification_handles_missing_fields():
    out = format_notification({})
    assert "Unknown sender" in out
    assert "\\(no subject\\)" in out  # parens are MarkdownV2-reserved
    assert "n/a" in out
    assert "⚪" in out  # urgency=None → grey emoji
