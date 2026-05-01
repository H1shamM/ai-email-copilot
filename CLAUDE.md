# AI Email Copilot — Claude Code Guide

Personal Gmail assistant powered by Claude. FastAPI backend, SQLite store, Telegram as the user interface (the original Flask web UI was dropped — see `docs/PROGRESS.md` Week 3 pivot note).

## Stack

- **Python 3.11+** (CI matrix runs on this)
- **FastAPI + uvicorn** — `app/main.py` exposes REST endpoints + the Telegram webhook
- **Anthropic SDK** — Claude Sonnet 4 for email analysis and (Story C) reply generation
- **Gmail API** — read + modify + send scopes via OAuth (`app/gmail/auth.py`)
- **python-telegram-bot ≥21** — webhook mode (no long-polling), wired through FastAPI
- **SQLite** — single `email_assistant.db` file, schema in `app/database/db.py::init_db`
- **pytest + pytest-asyncio + pytest-cov** — tests under `tests/unit/`

## Layout

```
app/
  main.py              # FastAPI app, REST endpoints, Telegram webhook route
  ai/
    analyzer.py        # Claude email analysis (lazy client singleton)
  database/
    db.py              # SQLite connection, schema, all DB helpers
  gmail/
    auth.py            # OAuth flow + token.pickle handling
    service.py         # Gmail API wrappers (fetch, parse)
  models/
    schemas.py         # Pydantic models
  telegram/
    bot.py             # Application singleton + lifecycle helpers
    handlers.py        # Command handlers + @authorized_only decorator
    formatting.py      # MarkdownV2 escaping + 4096-char chunking
tests/unit/            # All tests live here; no integration/e2e dirs yet
docs/                  # PRD, PROGRESS, GITHUB_WORKFLOW, templates
.claude/skills/        # Project-specific Claude Code skills (see below)
.claude/plans/         # Multi-story implementation plans
```

## Workflow — every change goes through this loop

1. **Open a GitHub issue** via the `create-user-story` or `create-bug` skill (don't write the body freehand — mirror `docs/USER_STORY_TEMPLATE.md`).
2. **Branch off `main`**:
   - Stories: `feature/<short-kebab>`
   - Bugs: `fix/<short-kebab>`
3. **Implement + test locally.** Run the pre-push trio before pushing:
   ```bash
   .venv/Scripts/black app/ tests/
   .venv/Scripts/flake8 app/ tests/ --max-line-length=100
   .venv/Scripts/pytest tests/ --cov=app
   ```
4. **Ship via the `pr-workflow` skill** — push, open PR with `Closes #<N>` in body, watch CI, squash-merge, delete branch, sync acceptance criteria, post completion report, update `docs/PROGRESS.md`.

Full conventions live in `docs/GITHUB_WORKFLOW.md`. Don't bypass: skipping `Closes #N` leaves orphan issues; skipping `PROGRESS.md` updates makes weekly status meaningless.

## Code standards (enforced by CI)

- **Type hints on every public function** (use Python 3.10+ syntax: `int | None`, `list[dict]`).
- **Docstrings on every public function** — one short line covering the *why* if non-obvious; well-named identifiers already explain the *what*.
- **black** with `line-length = 100` (configured in `pyproject.toml`).
- **flake8** clean.
- **Coverage ≥80%** — `pyproject.toml` has `fail_under = 80`. Live-network paths (OAuth, real Gmail/Telegram I/O) are excluded via `# pragma: no cover` and the `omit` list.
- **No comments on what the code does.** Only add a comment when the *why* is non-obvious (hidden constraint, workaround, surprising invariant).

## Conventions

- **`app/` not `src/`.** All Python code lives under `app/`.
- **snake_case** for files, functions, variables.
- **Secrets via `.env`**, never committed. `.env.example` lists every required key with placeholder values.
- **Lazy singletons for SDK clients** (see `analyzer._get_client()` and `bot.get_application()`) so env vars are read after `load_dotenv()`.
- **Imports in `app/main.py` use `# noqa: E402`** because `load_dotenv()` must run before any module that reads env vars at import time.
- **DB connections close in a `finally` block** (every helper in `db.py` follows this pattern).
- **Telegram handlers wrap with `@authorized_only`** — single-user auth via `TELEGRAM_AUTHORIZED_CHAT_ID`. Unauthorized chats get silent drops, never a leak reply.
- **MarkdownV2 escape every user-supplied field** before `reply_text(..., parse_mode=ParseMode.MARKDOWN_V2)` — use `app/telegram/formatting.escape_markdown_v2`.

## Common tasks

### Add a new Telegram command
1. Add an `async def` handler in `app/telegram/handlers.py`, decorate with `@authorized_only`.
2. Register it in `handlers.register()` with `application.add_handler(CommandHandler("name", fn))`.
3. Update the `WELCOME` string so `/help` lists the new command.
4. Add tests in `tests/unit/test_telegram_handlers.py` (mock `gmail_fetch_recent`, `db.*`, `analyze_email` — never hit real services).
5. If the response is user-facing rich text, route it through `formatting.py` so escaping + chunking are consistent.

### Add a new Claude AI feature
1. Create or extend a module under `app/ai/`, mirroring `analyzer.py`'s pattern: lazy `_get_client()`, prompt as a module constant, function returns parsed dict or `None` on failure.
2. Catch `json.JSONDecodeError` separately from generic `Exception` so JSON shape bugs are debuggable.
3. Tests: mock `_get_client()` to return a stub with `messages.create(...).content[0].text`. Never call the real API in tests.
4. The model ID is currently `claude-sonnet-4-20250514` — keep model selection in one place if you add a second AI module.

### Add a database migration
The schema lives entirely in `init_db()` in `app/database/db.py` as `CREATE TABLE IF NOT EXISTS ...`. For prototype velocity:
1. Add the new table or column to `init_db()`.
2. For schema changes on an existing column, drop and recreate the local DB during dev (`rm email_assistant.db && python -c "from app.database.db import init_db; init_db()"`).
3. Add a helper function for the new table; mirror the `try/finally: conn.close()` pattern.
4. Update `tests/unit/test_db.py`.
5. We don't have Alembic yet — when production deployment lands, that becomes a follow-up.

### Test Gmail / Claude / Telegram integration
**Never hit real services in unit tests.** Patterns already in the suite:
- Gmail fetch: `monkeypatch.setattr(handlers, "gmail_fetch_recent", lambda **_: [...])`
- Claude: `monkeypatch.setattr(handlers, "analyze_email", lambda _: {...})` or patch `_get_client` for analyzer-level tests
- Telegram updates: build a `MagicMock` Update with `.effective_chat.id` and `.message.reply_text = AsyncMock()`
- DB: most helpers are tested against the real SQLite file with a `monkeypatch.setenv("DATABASE_PATH", ":memory:")` pattern (see `test_db.py`)

For real-world manual verification, see the runbook in `docs/PROGRESS.md` Week 3 and the `~/.claude/plans/` files.

## Required environment variables

Listed in `.env.example`. Don't commit real values.

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API |
| `GMAIL_CREDENTIALS_PATH` | Path to OAuth client secrets JSON (default `credentials.json`) |
| `DATABASE_PATH` | SQLite file path (default `email_assistant.db`) |
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `TELEGRAM_AUTHORIZED_CHAT_ID` | Your chat ID from @userinfobot |
| `TELEGRAM_WEBHOOK_URL` | Public HTTPS URL Telegram POSTs to (use cloudflared/ngrok in dev) |
| `TELEGRAM_WEBHOOK_SECRET` | Random string shared with Telegram for request authentication |

`token.pickle` (Gmail OAuth) is generated on first auth and refreshed automatically. If `invalid_grant` errors appear, the refresh token has been revoked (Google revokes tokens for "Testing" apps after ~7 days of inactivity) — delete `token.pickle` and re-run `python -c "from app.gmail.auth import get_credentials; get_credentials()"` to re-auth.

## Project-specific Claude Code skills

Defined under `.claude/skills/`:

- **`create-user-story`** — File a single INVEST-structured GitHub issue using `docs/USER_STORY_TEMPLATE.md`.
- **`create-bug`** — File a bug report using `docs/BUG_REPORT_TEMPLATE.md`.
- **`pr-workflow`** — Push branch → open PR → watch CI → merge → close issue → update `PROGRESS.md`. Autonomous after PR creation.
- **`github`** — Conventions for using `gh` CLI in this repo (always derive `owner/repo` from `git remote`).

Use these instead of writing freehand `gh` commands.

## Key reference files

- **`docs/PRD.md`** — 7-week product plan and feature specs.
- **`docs/PROGRESS.md`** — Week-by-week task tracking, current status, engineering decisions log. **Update on every merge.**
- **`docs/GITHUB_WORKFLOW.md`** — Branch / commit / PR conventions in detail.
- **`docs/USER_STORY_TEMPLATE.md`** / **`docs/BUG_REPORT_TEMPLATE.md`** — Canonical issue bodies.
- **`pyproject.toml`** — black, pytest, coverage, mypy config (single source of truth for tooling thresholds).

## Current status (Week 3, in flight)

Week 3 pivoted from web UI to Telegram-only on 2026-04-24. Story breakdown:

- ✅ Story A — Telegram bot scaffolding + webhook + single-user auth (PR #14, 2026-04-30)
- ✅ Story B — Pull commands `/unread`, `/analyze`, `/inbox` (PR #16, 2026-05-01)
- 🔲 Story C — Draft reply generation + approve-before-send flow
- 🔲 Story D — Push notifications for high-priority emails

Detailed plan: `~/.claude/plans/concurrent-napping-crescent.md`.