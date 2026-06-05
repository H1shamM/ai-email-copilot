"""Learn the user's writing voice from Sent mail, for personalized replies.

The pure helpers (cleaning, selection, staleness) are unit-tested; the live Gmail
fetch in `get_voice_samples` is `# pragma: no cover` like the rest of gmail I/O.
"""

import json
import logging
import re
from datetime import datetime, timedelta

from app.database import db
from app.gmail.service import get_sent_emails

logger = logging.getLogger(__name__)

_PREF_SAMPLES = "voice_samples"
_PREF_UPDATED = "voice_samples_at"

MAX_SAMPLES = 5
MIN_SAMPLE_CHARS = 80
MAX_SAMPLE_CHARS = 800
REFRESH_DAYS = 7

# Strip the quoted-original trailer ("On <date>, X wrote:" + everything after) and
# any ">"-prefixed quote lines, so only the user's own writing remains.
_ON_WROTE_RE = re.compile(r"\nOn .{0,120}?wrote:.*", re.S)
_QUOTE_LINE_RE = re.compile(r"^\s*>.*$", re.M)


def clean_sent_body(body: str | None) -> str:
    """Return only the user's own text from a sent email body (quotes removed)."""
    if not body:
        return ""
    body = _ON_WROTE_RE.sub("", body)
    body = _QUOTE_LINE_RE.sub("", body)
    return body.strip()


def select_samples(sent_emails: list[dict]) -> list[str]:
    """Pick up to MAX_SAMPLES clean, reasonably-sized writing samples."""
    samples: list[str] = []
    for email in sent_emails:
        text = clean_sent_body(email.get("body") or email.get("snippet") or "")
        if MIN_SAMPLE_CHARS <= len(text) <= MAX_SAMPLE_CHARS:
            samples.append(text)
        if len(samples) >= MAX_SAMPLES:
            break
    return samples


def _is_stale(updated_at: str | None) -> bool:
    """True if the cached voice is missing or older than REFRESH_DAYS."""
    if not updated_at:
        return True
    try:
        return datetime.fromisoformat(updated_at) < datetime.now() - timedelta(days=REFRESH_DAYS)
    except ValueError:
        return True


def get_voice_samples(force_refresh: bool = False) -> list[str]:  # pragma: no cover
    """Cached writing samples, refreshed from Sent mail when stale or forced.

    Returns an empty list (→ generic replies) if there's no sent history or the
    fetch fails — personalization is best-effort, never blocking.
    """
    if not force_refresh and not _is_stale(db.get_preference(_PREF_UPDATED)):
        cached = db.get_preference(_PREF_SAMPLES)
        if cached:
            try:
                return json.loads(cached)
            except json.JSONDecodeError:
                logger.warning("Corrupt voice cache; re-learning from Sent")

    try:
        sent = get_sent_emails()
    except Exception:  # noqa: BLE001 — personalization is optional; fall back to generic
        logger.exception("Failed to fetch Sent mail for voice; using generic replies")
        return []

    samples = select_samples(sent)
    db.set_preference(_PREF_SAMPLES, json.dumps(samples))
    db.set_preference(_PREF_UPDATED, datetime.now().isoformat())
    return samples
