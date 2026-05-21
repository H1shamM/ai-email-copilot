"""Integration test for app.ai.agent against the real Claude API.

Run with: pytest -m integration tests/integration/test_agent_integration.py
"""

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="Requires ANTHROPIC_API_KEY for a live Claude call",
    ),
]


def test_agent_invokes_a_tool_on_a_clear_instruction():
    """A 'list my recent emails' instruction should make the model call a tool."""
    from app.ai import agent

    client = agent._get_client()
    response = client.messages.create(
        model=agent.MODEL,
        max_tokens=agent.MAX_TOKENS,
        system=agent.SYSTEM_PROMPT,
        tools=agent.TOOLS,
        messages=[{"role": "user", "content": "List my 3 most recent emails."}],
    )

    assert response.stop_reason == "tool_use"
    tool_names = [b.name for b in response.content if getattr(b, "type", None) == "tool_use"]
    assert "list_recent_emails" in tool_names
