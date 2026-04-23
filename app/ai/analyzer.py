import json
import os

from anthropic import Anthropic

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


ANALYSIS_PROMPT = """Analyze this email and provide structured output in JSON format.

EMAIL:
From: {sender}
Subject: {subject}
Body: {body}

Respond ONLY with valid JSON (no markdown fences):
{{
  "summary": "2-3 sentence summary",
  "category": "Work|Personal|Newsletter|Finance|Travel|Shopping|Other",
  "sentiment": "Urgent|Casual|Formal",
  "action_required": "Reply|Schedule|Read|Archive|Flag",
  "urgency_score": 1-10,
  "key_dates": [],
  "key_people": []
}}"""


def analyze_email(email_data: dict) -> dict | None:
    """Send email to Claude for analysis and return structured result."""
    prompt = ANALYSIS_PROMPT.format(
        sender=email_data.get("sender", "Unknown"),
        subject=email_data.get("subject", "No subject"),
        body=email_data.get("body") or email_data.get("snippet", ""),
    )

    try:
        message = _get_client().messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text.strip()

        # Handle markdown fences just in case
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        return json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"Failed to parse analysis JSON: {e}")
        return None
    except Exception as e:
        print(f"Claude API error: {e}")
        return None
