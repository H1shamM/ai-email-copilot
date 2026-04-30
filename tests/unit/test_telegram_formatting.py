"""Tests for app/telegram/formatting.py — escaping, renderers, chunking."""

from app.telegram.formatting import (
    chunk_messages,
    escape_markdown_v2,
    format_analysis_entry,
    format_inbox_entry,
    format_unread_entry,
)


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
    email = {"sender": "alice@example.com", "subject": "Hi", "snippet": "Just checking in"}
    block = format_unread_entry(email, 1)
    assert "*1\\.*" in block
    assert "alice@example\\.com" in block
    assert "*Subject:* Hi" in block
    assert "Just checking in" in block


def test_format_unread_entry_handles_missing_fields():
    block = format_unread_entry({}, 2)
    assert "*2\\.*" in block
    assert "Unknown sender" in block
    assert "\\(no subject\\)" in block


def test_format_analysis_entry_high_urgency_gets_red():
    email = {"sender": "boss@corp.com", "subject": "URGENT"}
    analysis = {"category": "Work", "urgency_score": 10, "summary": "Reply ASAP"}
    block = format_analysis_entry(email, analysis, 1)
    assert block.startswith("🔴")
    assert "*Category:* Work" in block
    assert "10/10" in block
    assert "Reply ASAP" in block


def test_format_analysis_entry_medium_urgency_gets_yellow():
    block = format_analysis_entry({"sender": "x"}, {"urgency_score": 6}, 1)
    assert block.startswith("🟡")


def test_format_analysis_entry_low_urgency_gets_green():
    block = format_analysis_entry({"sender": "x"}, {"urgency_score": 2}, 1)
    assert block.startswith("🟢")


def test_format_analysis_entry_missing_urgency_shows_na():
    block = format_analysis_entry({"sender": "x"}, {"category": "Other"}, 1)
    assert block.startswith("⚪")
    assert "n/a" in block


def test_format_inbox_entry_happy_path():
    row = {
        "sender": "alice@example.com",
        "subject": "Update",
        "ai_summary": "All good.",
        "urgency_score": 9,
    }
    block = format_inbox_entry(row, 1)
    assert block.startswith("🔴")
    assert "alice@example\\.com" in block
    assert "Update" in block
    assert "All good\\." in block


def test_format_inbox_entry_handles_missing_analysis():
    block = format_inbox_entry({"sender": "x", "subject": "y"}, 1)
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
