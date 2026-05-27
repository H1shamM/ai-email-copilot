"""Unit tests for app.ai.agent — tool-use loop with mocked Anthropic client."""

from types import SimpleNamespace

from app.ai import agent


def _text(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _tool(tool_id: str, name: str, tool_input: dict) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input=tool_input)


def _response(stop_reason: str, content: list) -> SimpleNamespace:
    return SimpleNamespace(stop_reason=stop_reason, content=content)


class _FakeMessages:
    def __init__(self, responses: list, calls: list):
        self._responses = responses
        self.calls = calls

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _FakeClient:
    def __init__(self, responses: list):
        self.calls: list = []
        self.messages = _FakeMessages(list(responses), self.calls)


def _install(monkeypatch, responses: list) -> _FakeClient:
    client = _FakeClient(responses)
    monkeypatch.setattr(agent, "_get_client", lambda: client)
    return client


def test_read_only_tool_executes_and_feeds_result_back(monkeypatch):
    monkeypatch.setattr(
        agent.db,
        "get_recent_emails",
        lambda limit: [{"id": 1, "sender": "a@a", "subject": "Hi", "snippet": "x"}],
    )
    client = _install(
        monkeypatch,
        [
            _response("tool_use", [_tool("t1", "list_recent_emails", {"limit": 3})]),
            _response("end_turn", [_text("Here are your emails.")]),
        ],
    )

    text, pending = agent.run_agent("list my emails")

    assert text == "Here are your emails."
    assert pending == []
    assert len(client.calls) == 2
    # The second call carried the tool_result back to the model.
    fed_back = client.calls[1]["messages"][-1]["content"][0]
    assert fed_back["type"] == "tool_result"
    assert '"subject": "Hi"' in fed_back["content"]


def test_mutating_tool_is_queued_not_executed(monkeypatch):
    sent = []
    monkeypatch.setattr(agent, "gmail_send_reply", lambda *a, **k: sent.append(a))
    _install(
        monkeypatch,
        [
            _response("tool_use", [_tool("t1", "send_reply", {"email_id": 5, "body": "Yes"})]),
            _response("end_turn", [_text("Proposed a reply.")]),
        ],
    )

    text, pending = agent.run_agent("reply yes to 5")

    assert sent == []  # nothing sent inside the loop
    assert pending == [{"name": "send_reply", "input": {"email_id": 5, "body": "Yes"}}]
    assert text == "Proposed a reply."


def test_clean_termination_no_tools(monkeypatch):
    client = _install(monkeypatch, [_response("end_turn", [_text("Nothing to do.")])])
    text, pending = agent.run_agent("hi")
    assert text == "Nothing to do."
    assert pending == []
    assert len(client.calls) == 1


def test_iteration_cap_stops_runaway_loop(monkeypatch):
    monkeypatch.setattr(agent.db, "get_recent_emails", lambda limit: [])

    class _Looping:
        def __init__(self):
            self.calls: list = []
            self.messages = self

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return _response("tool_use", [_tool("t", "list_recent_emails", {})])

    client = _Looping()
    monkeypatch.setattr(agent, "_get_client", lambda: client)

    text, pending = agent.run_agent("loop forever")

    # MAX_ITERATIONS tool rounds + one forced final-answer turn.
    assert len(client.calls) == agent.MAX_ITERATIONS + 1
    assert pending == []
    # A pathological loop that yields no text still returns a usable fallback,
    # never an empty/dangling response.
    assert text == agent.CAP_FALLBACK


def test_iteration_cap_forces_final_answer(monkeypatch):
    """Hitting the cap mid-loop must synthesize a real answer, not return interim text."""
    monkeypatch.setattr(agent.db, "get_recent_emails", lambda limit: [])
    # Every in-loop round emits interim narration alongside a tool call (never a clean stop).
    responses = [
        _response(
            "tool_use",
            [_text("Now let me analyze each email…"), _tool(f"t{i}", "list_recent_emails", {})],
        )
        for i in range(agent.MAX_ITERATIONS)
    ]
    # The forced, tool-free turn returns the actual synthesized answer.
    responses.append(_response("end_turn", [_text("Here is the full breakdown.")]))
    client = _install(monkeypatch, responses)

    text, pending = agent.run_agent("be very thorough about every unread email")

    assert text == "Here is the full breakdown."  # not the interim "Now let me analyze…"
    assert pending == []
    assert len(client.calls) == agent.MAX_ITERATIONS + 1
    # The final turn disables further tool use so the model must produce text.
    assert client.calls[-1].get("tool_choice") == {"type": "none"}


def test_unknown_tool_returns_error_result(monkeypatch):
    client = _install(
        monkeypatch,
        [
            _response("tool_use", [_tool("t1", "no_such_tool", {})]),
            _response("end_turn", [_text("done")]),
        ],
    )
    text, pending = agent.run_agent("do something weird")
    fed_back = client.calls[1]["messages"][-1]["content"][0]["content"]
    assert fed_back.startswith("ERROR: unknown tool")
    assert pending == []
    assert text == "done"


def test_tool_exception_returns_error_result(monkeypatch):
    def boom(_):
        raise RuntimeError("db down")

    monkeypatch.setattr(agent.db, "get_email_by_row_id", boom)
    client = _install(
        monkeypatch,
        [
            _response("tool_use", [_tool("t1", "get_email", {"email_id": 1})]),
            _response("end_turn", [_text("ok")]),
        ],
    )
    agent.run_agent("get email 1")
    fed_back = client.calls[1]["messages"][-1]["content"][0]["content"]
    assert fed_back.startswith("ERROR: tool get_email failed")


def test_draft_reply_is_read_only(monkeypatch):
    monkeypatch.setattr(agent.db, "get_email_by_row_id", lambda _: {"id": 5, "sender": "a@a"})
    monkeypatch.setattr(agent, "regenerate_one", lambda email, tone: "Draft text here.")
    client = _install(
        monkeypatch,
        [
            _response("tool_use", [_tool("t1", "draft_reply", {"email_id": 5})]),
            _response("end_turn", [_text("Here's a draft.")]),
        ],
    )
    text, pending = agent.run_agent("draft a reply to 5")
    assert pending == []  # drafting does not require approval
    fed_back = client.calls[1]["messages"][-1]["content"][0]["content"]
    assert "Draft text here." in fed_back


def test_execute_action_send_reply(monkeypatch):
    monkeypatch.setattr(
        agent.db, "get_email_by_row_id", lambda _: {"thread_id": "th", "gmail_message_id": "gm"}
    )
    sent = []
    monkeypatch.setattr(agent, "gmail_send_reply", lambda t, m, b: sent.append((t, m, b)))

    result = agent.execute_action({"name": "send_reply", "input": {"email_id": 5, "body": "Hi"}})

    assert sent == [("th", "gm", "Hi")]
    assert "Reply sent to email 5" in result


def test_execute_action_send_reply_missing_email(monkeypatch):
    monkeypatch.setattr(agent.db, "get_email_by_row_id", lambda _: None)
    result = agent.execute_action({"name": "send_reply", "input": {"email_id": 9, "body": "x"}})
    assert "not found" in result


def test_execute_action_create_calendar_event(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        agent.scheduler, "create_event", lambda row: captured.update(row) or "gid123"
    )
    result = agent.execute_action(
        {
            "name": "create_calendar_event",
            "input": {
                "title": "Sync",
                "start_iso": "2026-05-25T15:00:00Z",
                "duration_minutes": 45,
            },
        }
    )
    assert captured["event_date"] == "2026-05-25"
    assert captured["event_time"] == "15:00:00"
    assert captured["duration_minutes"] == 45
    assert "Calendar event created: Sync (gid123)" in result


def test_execute_action_unknown():
    assert "Unknown action" in agent.execute_action({"name": "frobnicate", "input": {}})


def test_describe_action_summaries():
    send = agent.describe_action(
        {"name": "send_reply", "input": {"email_id": 5, "body": "Sounds good"}}
    )
    assert "email 5" in send and "Sounds good" in send
    event = agent.describe_action(
        {
            "name": "create_calendar_event",
            "input": {"title": "Sync", "start_iso": "2026-05-25T15:00:00Z"},
        }
    )
    assert "Sync" in event and "2026-05-25T15:00:00Z" in event
