"""Prompt templates for the reply generator.

Kept in their own module so they're trivial to unit-test (no Anthropic SDK
import) and easy to iterate on without touching the generator logic.
"""

TONES: tuple[str, ...] = ("professional", "friendly", "brief")

TONE_INSTRUCTIONS: dict[str, str] = {
    "professional": (
        "Formal, detailed, and polite. Use professional language and a clear "
        "salutation/sign-off. Keep paragraphs tight."
    ),
    "friendly": (
        "Warm, conversational, and casual — sounds like a friend writing back. "
        "Avoid jargon. Light contractions are fine."
    ),
    "brief": (
        "Under three sentences. Direct, no filler. Skip the salutation if it "
        "would push the message over three sentences."
    ),
}


REPLY_PROMPT = """Generate a {tone} email reply.

ORIGINAL EMAIL:
From: {sender}
Subject: {subject}
Body: {body}

TONE INSTRUCTIONS:
{tone_instructions}

Rules:
- Address every question or request in the original email.
- Sound natural and human; do not mention that you are an AI.
- Do NOT include the subject line, "From:", "To:", or any email headers.
- Output ONLY the reply body. No markdown fences, no preamble, no JSON.

REPLY:"""


def build_reply_prompt(email: dict, tone: str) -> str:
    """Render the prompt for a single tone. Raises on unknown tone."""
    if tone not in TONE_INSTRUCTIONS:
        raise ValueError(f"Unknown tone {tone!r}; allowed: {sorted(TONE_INSTRUCTIONS)}")
    return REPLY_PROMPT.format(
        tone=tone,
        sender=email.get("sender", "Unknown"),
        subject=email.get("subject", "(no subject)"),
        body=email.get("body") or email.get("snippet", ""),
        tone_instructions=TONE_INSTRUCTIONS[tone],
    )
