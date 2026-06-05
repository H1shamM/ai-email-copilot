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
    "voice": (
        "Reply naturally in my own voice and typical length — match the greeting, "
        "phrasing, and sign-off from my writing examples below."
    ),
}

# Nudges that tweak a generated draft on demand (the Shorter/Warmer buttons).
REPLY_MODIFIERS: dict[str, str] = {
    "shorter": "Make this reply noticeably shorter and more direct.",
    "warmer": "Make this reply warmer, friendlier, and more personable.",
}


REPLY_PROMPT = """Generate a {tone} email reply.

ORIGINAL EMAIL:
From: {sender}
Subject: {subject}
Body: {body}

TONE INSTRUCTIONS:
{tone_instructions}
{style_block}
Rules:
- Address every question or request in the original email.
- Sound natural and human; do not mention that you are an AI.
- Do NOT include the subject line, "From:", "To:", or any email headers.
- Output ONLY the reply body. No markdown fences, no preamble, no JSON.

REPLY:"""


def _style_block(style_samples: list[str] | None) -> str:
    """A prompt section showing the user's own past emails to mimic their voice."""
    if not style_samples:
        return ""
    examples = "\n\n---\n\n".join(style_samples)
    return (
        "\nMY WRITING VOICE — match my vocabulary, greeting, phrasing, and sign-off. "
        "These are real emails I have written:\n"
        f"{examples}\n"
    )


def build_reply_prompt(
    email: dict,
    tone: str,
    style_samples: list[str] | None = None,
    modifier: str | None = None,
) -> str:
    """Render the prompt for a single tone, optionally in the user's voice + a nudge."""
    if tone not in TONE_INSTRUCTIONS:
        raise ValueError(f"Unknown tone {tone!r}; allowed: {sorted(TONE_INSTRUCTIONS)}")
    instructions = TONE_INSTRUCTIONS[tone]
    if modifier:
        if modifier not in REPLY_MODIFIERS:
            raise ValueError(f"Unknown modifier {modifier!r}; allowed: {sorted(REPLY_MODIFIERS)}")
        instructions = f"{instructions} {REPLY_MODIFIERS[modifier]}"
    return REPLY_PROMPT.format(
        tone=tone,
        sender=email.get("sender", "Unknown"),
        subject=email.get("subject", "(no subject)"),
        body=email.get("body") or email.get("snippet", ""),
        tone_instructions=instructions,
        style_block=_style_block(style_samples),
    )
