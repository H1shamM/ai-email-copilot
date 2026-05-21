"""AI package — shared config for the Claude-backed modules."""

# Single source of truth for the model id. analyzer/meeting_detector/reply_generator
# still hardcode this string; centralizing them here is a tracked follow-up.
MODEL = "claude-sonnet-4-20250514"
