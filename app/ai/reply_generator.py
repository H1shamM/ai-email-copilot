"""AI reply generation: turn an email into 3 tone-specific drafts.

Mirrors the lazy-singleton + error-handling pattern from `analyzer.py`.
JSONDecodeError is intentionally caught separately from generic Exception
so future schema changes are debuggable.
"""

import os

from anthropic import Anthropic

from app.ai.prompts import TONES, build_reply_prompt

MODEL_ID = "claude-sonnet-4-20250514"
MAX_TOKENS = 1024

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    """Lazy Anthropic client so the API key is read after load_dotenv()."""
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def _generate_one(email: dict, tone: str) -> str | None:
    """Generate a single reply or return None on API failure."""
    prompt = build_reply_prompt(email, tone)
    try:
        message = _get_client().messages.create(
            model=MODEL_ID,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:  # noqa: BLE001 — log + return None, caller decides UX
        print(f"Claude reply generation failed for tone={tone}: {e}")
        return None

    text = message.content[0].text.strip()
    return _strip_fences(text) or None


def _strip_fences(text: str) -> str:
    """Remove leading/trailing ``` fences if Claude added them anyway."""
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json") or text.startswith("text"):
                text = text.split("\n", 1)[1] if "\n" in text else ""
    return text.strip()


def generate_replies(email: dict, tones: tuple[str, ...] = TONES) -> dict[str, str]:
    """Return {tone: draft_text} for every tone that succeeded.

    Tones whose API call failed are omitted from the returned dict, so
    callers can render partial results rather than blocking on a full retry.
    """
    out: dict[str, str] = {}
    for tone in tones:
        draft = _generate_one(email, tone)
        if draft:
            out[tone] = draft
    return out


def regenerate_one(email: dict, tone: str) -> str | None:
    """Regenerate a single tone — used by the Telegram 'Regenerate' button."""
    return _generate_one(email, tone)
