# Email Assistant - Development Progress

**Project Start:** March 15, 2026  
**Target Completion:** May 9, 2026  
**Current Week:** Week 3

---

## ✅ Week 1: Setup & Project Definition (Mar 15-21) - COMPLETE

- [x] Development environment setup
- [x] Gmail API credentials obtained
- [x] OAuth 2.0 authentication working
- [x] Can fetch emails from Gmail
- [x] Basic project structure created
- [x] Git repository initialized

**Deliverable:** ✅ Can authenticate and read emails

---

## ✅ Week 2: Integration POC + System Design (Mar 22-28) - COMPLETE

- [x] Database schema designed and implemented
- [x] SQLite database setup
- [x] Email fetching script (last 10 unread)
- [x] Claude API integration working
- [x] Email analysis (summary + category) functional
- [x] System architecture documented

**Deliverable:** ✅ Can fetch 10 emails and get AI summaries

---

## ✅ Week 3: Telegram Integration + Draft Replies (Apr 5 – May 5) - COMPLETE

**Pivot (2026-04-24):** Original plan was Flask web UI. Replaced with **Telegram-only interface** (webhook into FastAPI, single-user auth, approve-before-send for replies, push notifications for important emails). Detailed plan: `~/.claude/plans/concurrent-napping-crescent.md`.

**Goal:** Use the Email Copilot entirely from Telegram — pull commands + push notifications + draft reply approval flow.

### Tasks Breakdown

#### Story A: Telegram bot scaffolding + webhook + single-user auth
**Branch:** `feature/telegram-bot-scaffolding`
**Status:** ✅ Complete (PR #14, 2026-04-30)
**Size:** M
**Scope:**
- Add `python-telegram-bot>=21.0` dep
- `app/telegram/{bot,handlers}.py` — Application instance, `/start`, `/help`, auth guard decorator
- `POST /telegram/webhook` in `app/main.py` with `secret_token` verification
- Auto-register webhook with Telegram on FastAPI startup
- `telegram_users` table in `app/database/db.py`
- Single-user auth via `TELEGRAM_AUTHORIZED_CHAT_ID` env var; unauthorized chats silently dropped

---

#### Story B: Pull commands — `/unread`, `/analyze`, `/inbox`
**Branch:** `feature/telegram-pull-commands`
**Status:** ✅ Complete (PR #16, 2026-05-01)
**Size:** M
**Scope:**
- `/unread` — fetch + return numbered list with sender/subject/snippet
- `/analyze` — run Claude on unprocessed emails, return per-email category/priority/summary
- `/inbox` — last N analyzed emails from DB with priority indicators
- `app/telegram/formatting.py` — MarkdownV2 escaping, 4096-char chunking

---

#### Story C: Draft reply generation + approve-before-send (subsumes original Task 1)
**Branch:** `feature/telegram-reply-flow`
**Status:** ✅ Complete (PR #19, 2026-05-05)
**Size:** L
**Scope:**
- `app/ai/reply_generator.py` — 3-tone replies (professional / friendly / brief)
- `app/ai/prompts.py` — externalize tone prompt templates
- `app/gmail/service.py` — add `send_reply(thread_id, message_id, body)` with `In-Reply-To` header
- `app/database/db.py` — `insert_draft_reply`, `update_draft_status`, `get_draft_by_id`
- `/reply <email_id>` command shows 3 drafts with inline keyboard: Approve / Edit / Skip / Regenerate
- `app/telegram/conversations.py` — `ConversationHandler` for the edit flow
- Approve → `send_reply()` → mark sent in DB

---

#### Story D: Push notifications for important emails
**Branch:** `feature/telegram-push-notifications`
**Status:** ✅ Complete (PR #21, 2026-05-05)
**Size:** M
**Scope:**
- Add `apscheduler` dep
- `app/telegram/push.py` — scheduled job: every `TELEGRAM_PUSH_INTERVAL_MINUTES` minutes, fetch unread → analyze → notify if priority ≥ 4
- `notified_at` column on `emails` table
- Notification includes sender / subject / summary + inline "Generate Reply" + "Mark Done" buttons
- `/pause` and `/resume` commands toggle scheduler

---

### Already Shipped (during bootstrap)

- ✅ **CI/CD** (was Task 7) — `tests.yml` + `lint.yml` shipped 2026-04-23 in #10
- ✅ **REST API pipeline** (was Task 4 backend) — fetch/analyze endpoints shipped in #8 (kept for backend testing; not the UX)

---

### Week 3 Success Criteria

By end of week, must demonstrate:
- [x] Authorized user can `/start` and get a welcome from the bot (Story A)
- [x] `/unread` and `/analyze` return formatted email summaries in Telegram (Story B)
- [x] `/reply <id>` flow generates 3 drafts and sends via Gmail after approval (Story C)
- [x] Bot proactively notifies on priority ≥ 4 emails (Story D)
- [x] Coverage stays ≥80% (final: 91.94%)
- [x] CI green on every PR

**Deliverable:** ✅ Email Copilot fully driven from Telegram — shipped 2026-05-05

---

## ✅ Week 4: Calendar Integration (May 10–21) - COMPLETE

**Pivot back from Week 6:** with AWS deploy + auto-deploy live, returning to feature work. Week 4 PRD-aligned scope (Feature 5 — Google Calendar) ahead of Week 5 (Agentic).

### Stories
- ✅ **Story W4-A** ([#34](https://github.com/H1shamM/ai-email-copilot/issues/34) / PR [#35](https://github.com/H1shamM/ai-email-copilot/pull/35)) — Calendar OAuth scope + `app/calendar/service.py` wrappers + `calendar_events.status` migration + DB helpers
- ✅ **Story W4-B** ([#36](https://github.com/H1shamM/ai-email-copilot/issues/36) / PR [#37](https://github.com/H1shamM/ai-email-copilot/pull/37)) — Meeting detection from email body (Claude-driven NL date resolution) + idempotent persistence into `calendar_events`
- ✅ **Story W4-C** ([#38](https://github.com/H1shamM/ai-email-copilot/issues/38) / PR [#39](https://github.com/H1shamM/ai-email-copilot/pull/39)) — Telegram `/schedule` flow (list-only) with approve-before-create + block-on-conflict free/busy check; new `app/calendar/scheduler.py` orchestration
- ✅ **Event thread context** (post-Demo-Day) ([#72](https://github.com/H1shamM/ai-email-copilot/issues/72) / PR [#73](https://github.com/H1shamM/ai-email-copilot/pull/73)) — booked events now carry a `description` = email `ai_summary` + Gmail deep link (`#all/<thread_id>`), so each meeting is self-explanatory on the calendar. First quick win on the **inbox-native scheduling ("Calendly replacement")** direction surfaced at Demo Day. Next on that track: `/today` agenda digest, then availability-negotiation drafts (Week 5 agentic).

#### Calendar QA pass (2026-06-04) — bugs found via live Chrome-MCP test + injected mock meetings
- ✅ **Detection gate too strict** ([#74](https://github.com/H1shamM/ai-email-copilot/issues/74) / PR [#75](https://github.com/H1shamM/ai-email-copilot/pull/75)) — `maybe_detect_meeting` only fired on `action_required == "Schedule"`, but the analyzer tags most meeting invites `Reply` → silently dropped. Now gates on `{Schedule, Reply}` with the detector's `is_meeting`+confidence as the authority.
- ✅ **`/schedule` Create failed silently** ([#76](https://github.com/H1shamM/ai-email-copilot/issues/76) / PR [#78](https://github.com/H1shamM/ai-email-copilot/pull/78)) — the freebusy `has_conflict()` call ran outside the try/except, so a Calendar API error (here: **Calendar API disabled in GCP project `707808781459`** — needs enabling in the console) escaped into the background webhook task and the user got no feedback. Guarded the conflict check (`Create failed: <exc>`, status left retryable) + added a global `add_error_handler` safety net.
- 🔲 **Stale past-dated `/schedule` entries** ([#77](https://github.com/H1shamM/ai-email-copilot/issues/77)) — `schedule_command` lists detected events with no past-date filter; old detections (e.g. May 28, Jun 1) re-appear forever. Open.
- ⚠️ **Action item (user):** enable the Google Calendar API for the GCP project so `/schedule` Create can actually book events.

### Re-auth required after Story W4-A merges

Adding `https://www.googleapis.com/auth/calendar` to `SCOPES` invalidates any existing `token.pickle`. After pulling the merged change:

```powershell
Remove-Item token.pickle -ErrorAction SilentlyContinue
.venv/Scripts/python -c "from app.gmail.auth import get_credentials; get_credentials()"
```

The browser flow now lists Calendar alongside the Gmail scopes — grant it. Subsequent runs reuse the refreshed token transparently.

---

## 🔄 Week 5: Agentic Workflows (started 2026-05-21) - IN PROGRESS

**Showcase centerpiece:** the agent satisfies the program's "advanced LLM use" threshold via **both Function Calling and Agentic Flow**, orchestrating the existing Gmail + Calendar + DB capabilities behind one natural-language command.

### Stories
- ✅ **Story W5-A** ([#40](https://github.com/H1shamM/ai-email-copilot/issues/40) / PR [#41](https://github.com/H1shamM/ai-email-copilot/pull/41)) — Agentic `/agent` command: native Anthropic tool-use loop in `app/ai/agent.py`; read-only tools (list/get/analyze emails, check availability, draft reply) auto-execute, mutating tools (send reply / create event) queued for approve-before-act; iteration cap + error-tolerant tool results
- 🔲 **Story W5-B** — Priority scoring / inbox triage (deterministic score, exposed as an agent tool + `/triage`)
- 🔲 **Story W5-C** — Follow-up tracking + reminders (`followups` table → helpers + scheduler tick + agent tools)
- 🔲 **Story W5-D** — Bulk actions (e.g. "archive all newsletters") as gated agent tools

**Deferred from W5-A scope:** natural-language passthrough (routing non-command messages to the agent); centralizing the `MODEL` constant into `analyzer`/`meeting_detector`/`reply_generator`.

---

## 🔄 Week 6: Deployment to AWS (May 5 onwards) - IN PROGRESS

**Pivot:** original "UI & Demo" Week 6 was already covered by Week 3's Telegram pivot. Repurposing Week 6 to ship the bot to AWS so it's no longer tethered to a laptop + cloudflared tunnel.

### Stories

#### Story W6-A: Provision EC2 + first manual deploy
**Branch:** `feature/aws-deploy-runbook` (Track 2) + manual provisioning (Track 1)
**Status:** ✅ Complete (PR #29 + Track 1 deploy on 2026-05-07)
**Size:** M
**Live at:** `https://79-125-102-15.nip.io/`

**Scope shipped:**
- t4g.nano EC2 in eu-west-1 with attached EIP, Ubuntu 24.04 LTS arm64, SSM-only access (no SSH)
- Caddy reverse proxy with auto-TLS via Let's Encrypt, hostname `<eip>.nip.io`
- systemd unit (`copilot.service`) running uvicorn under a hardened `copilot` system user
- `GET /health` endpoint returning `{"ok": true}`
- Full runbook in `docs/AWS_DEPLOY.md` covering provision → bootstrap → smoke test → teardown
- Templates in `infra/` (`Caddyfile.template`, `copilot.service`)

**Bugs caught during the live deploy** (runbook patched in main):
1. `b0084fb` — em-dash in SG description rejected by AWS (ASCII-only field)
2. `a5f0bf7` — Caddyfile placeholder substitution shouldn't be hand-edited; switched to IMDSv2-driven `sed` so the EIP is auto-detected
3. `5e3059c` — `sslip.io` was rate-limited by Let's Encrypt; switched default hostname to `nip.io`

#### Story W6-B: GitHub Actions auto-deploy on push to main
**Branch:** `feature/aws-deploy-ci-cd` (Track 2) + manual OIDC + role setup (Track 1)
**Status:** ✅ Complete (PR #31 merged 2026-05-07; first green deploy run #25499474023)
**Size:** M
**Scope shipped:**
- `.github/workflows/deploy.yml` — triggers on push to `main` + `workflow_dispatch`. Concurrency `deploy-prod` queues parallel pushes.
- **OIDC** auth (no long-lived AWS access keys in repo secrets); trust policy restricted to `repo:H1shamM/ai-email-copilot:ref:refs/heads/main`.
- IAM role `copilot-github-deploy` with minimal scope: `ssm:SendCommand` on the one instance + `AWS-RunShellScript` document, `ssm:GetCommandInvocation` on `*`.
- Deploy command on the instance: `git checkout <sha> && pip install -q -r requirements.txt && systemctl restart copilot`. Pinned to `${{ github.sha }}` so re-running an older workflow run rolls back to that commit.
- Smoke-check on `/health` after restart with 3 retries.
- Rollback documented: Actions UI → previous successful run → *Re-run all jobs*.

**Bugs caught during the live setup** (workflow + runbook patched in main):
- `ec379b8` — PowerShell parses `$ACCOUNT_ID:oidc-provider/...` as scope-modifier syntax, leaking an empty account ID into the Federated ARN. Switched the runbook to `${ACCOUNT_ID}` curly-brace form and added `Get-Content` sanity-checks.
- [PR #64](https://github.com/H1shamM/ai-email-copilot/pull/64) (`01a52c5`) — when an SSM deploy command ends in `Failed`/`Cancelled`/`TimedOut`, the workflow only dumped `StandardErrorContent`, which was empty for shell-chain failures that wrote the trace to stdout (e.g. `cd nonexistent`). Now dumps stdout alongside stderr so failures are diagnosable from the Actions log.

**Follow-ups noted but not blocking:**
- Node 20 deprecation warning on `aws-actions/configure-aws-credentials@v4`. Bumping to v5 (or opting into Node 24) before Sept 2026.
- Reboot survival test from W6-A still pending.

#### Story W6-C: Observability + OAuth health
**Branch:** `feature/aws-monitoring-oauth-health`
**Status:** 🔄 In progress — OAuth monitor shipped ([#44](https://github.com/H1shamM/ai-email-copilot/issues/44) / PR [#45](https://github.com/H1shamM/ai-email-copilot/pull/45)); CloudWatch + enriched `/health` still open
**Size:** M
**Scope:**
- ✅ **Gmail OAuth health monitor** (`app/telegram/oauth_monitor.py`) — scheduled non-interactive token check that DMs the user on the healthy→broken edge + on recovery; `auth.get_credentials()` now raises a clear error on `RefreshError` so `/unread` no longer fails silently. Driven by a real incident: revoked Testing-app token returned silence. Gated by `TELEGRAM_OAUTH_CHECK_ENABLED` / `_INTERVAL_HOURS`.
- 🔲 CloudWatch logs agent on instance; systemd unit logs to journald → CloudWatch
- 🔲 One alarm: "uvicorn unit not active for 5 min" → email
- 🔲 Enrich `/health` with DB connectivity + Telegram `getMe` (Gmail token validity is covered by the scheduled monitor — deliberately not a live call on the frequently-pinged `/health`)
- ✅ **Python root logger at INFO** ([#46](https://github.com/H1shamM/ai-email-copilot/issues/46) / PR [#47](https://github.com/H1shamM/ai-email-copilot/pull/47)) — `logging.basicConfig(level=LOG_LEVEL)` at startup so app + APScheduler `INFO` reach journald (verified: "OAuth monitor started" + scheduled `check_and_alert` now visible in `journalctl -u copilot`)

> Root cause of the OAuth incidents: the app is a Google "Testing" OAuth app, whose refresh tokens expire ~7 days after issuance. The monitor surfaces this early but cannot prevent it — the real fix is publishing the OAuth app (External → Production, needs Google verification for restricted Gmail scopes).

**Cost target:** ~$5/mo steady-state plus Anthropic API charges.

---

## 🐛 QA Hardening Pass (2026-05-24/25)

A senior-QA test pass of the live Telegram bot (driven through Telegram Web) exercised every command's happy path, edge cases, and error handling. No crashes or raw stack traces surfaced, but six defects were filed and fixed — two medium-severity, four low. Each shipped as its own branch/PR with unit tests; all merged to `main`.

| Issue | PR | Fix |
|---|---|---|
| [#48](https://github.com/H1shamM/ai-email-copilot/issues/48) | [#54](https://github.com/H1shamM/ai-email-copilot/pull/54) | Refuse to draft/send replies to **no-reply senders** — `is_no_reply_sender()` + draft-time gate in `_run_reply_flow` + send-time guard in `_send_draft`, replacing the previous non-deterministic (model-emergent) refusal |
| [#49](https://github.com/H1shamM/ai-email-copilot/issues/49) | [#55](https://github.com/H1shamM/ai-email-copilot/pull/55) | Reply to **unknown commands & plain text** instead of silently dropping them — `MessageHandler` fallbacks registered last so they don't shadow commands or the edit `ConversationHandler` |
| [#50](https://github.com/H1shamM/ai-email-copilot/issues/50) | [#56](https://github.com/H1shamM/ai-email-copilot/pull/56) | Clarify `/unread`'s list numbers aren't `/reply` ids (footer pointing to `/analyze` → `/inbox`) |
| [#51](https://github.com/H1shamM/ai-email-copilot/issues/51) | [#57](https://github.com/H1shamM/ai-email-copilot/pull/57) | Acknowledge **ignored extra arguments** on `/reply` and `/analyze` |
| [#52](https://github.com/H1shamM/ai-email-copilot/issues/52) | [#58](https://github.com/H1shamM/ai-email-copilot/pull/58) | Realistic `/reply` drafting **ETA** ("up to a minute" vs the old "~10s") |
| [#53](https://github.com/H1shamM/ai-email-copilot/issues/53) | [#59](https://github.com/H1shamM/ai-email-copilot/pull/59) | Deterministic `/inbox` **ordering** — `created_at DESC, id DESC` tiebreaker (not `received_date`, which stores an unsortable RFC 2822 string) |

**Follow-ups noted (not blocking):**
- #48 detection covers no-reply *patterns* but not automated senders lacking such a token (e.g. `jobs-listings@`).
- #53 true received-time ordering would need a parsed/ISO received timestamp stored on ingest.
- #52 could parallelize the three tone generations to actually shorten the wait.

**Second pass (2026-05-25):** A follow-up QA run via the `qa-test-telegram-bot` skill exercised all eight test suites (functional, edge cases, push, concurrency, recovery, integration, security, UX) and surfaced one medium finding plus three low cosmetic ones. The medium was filed and fixed:

| Issue | PR | Fix |
|---|---|---|
| [#61](https://github.com/H1shamM/ai-email-copilot/issues/61) | [#62](https://github.com/H1shamM/ai-email-copilot/pull/62) | `/agent` no longer returns an interim preamble when `run_agent` hits `MAX_ITERATIONS` mid-tool-loop — a tool-disabled (`tool_choice: none`) synthesis turn now runs, with an explicit `CAP_FALLBACK` if even that yields no text. Limits bumped (`MAX_TOKENS` 1024→2048, `MAX_ITERATIONS` 5→8) and the "🤖 Working on it…" status message is deleted once the result is ready, so it no longer lingers. |

Three lows left unfiled (raw `##`/`**` Markdown in agent replies; minor inconsistency between `/reply -1` "Usage" vs `/reply 0` "No email with id 0"; no rate-limiting on rapid identical commands — acceptable for single-user). Prompt-injection attempts via `/agent` were refused cleanly; no internals leaked.

Final suite after all merges: **263 passing, ~94% coverage.**

---

## 🔒 CI Security Scanning (2026-06-04)

Added three complementary security gates alongside the existing Lint + Tests workflows ([#65](https://github.com/H1shamM/ai-email-copilot/issues/65) / PR [#66](https://github.com/H1shamM/ai-email-copilot/pull/66)):

- **Bandit** (Python SAST) — `.github/workflows/security.yml`, scans `app/` at medium+ severity (`-ll`); required gate. Two intentional `B301` pickle loads in `app/gmail/auth.py` (app-written, local `token.pickle`) suppressed with documented `# nosec B301`.
- **Dependabot** — `.github/dependabot.yml`, weekly `pip` + `github-actions` update PRs (grouped, limit 5) plus CVE alerts.
- **Trivy** — filesystem `vuln,secret,misconfig` scan for HIGH/CRITICAL in the same workflow; **report-only** (`exit-code: 0`) for now.

**Follow-ups (not blocking):**
- Enable Dependabot alerts in repo **Settings → Code security** (manual, one-time).
- Flip Trivy to a gate (`exit-code: 1`) once the first scan's HIGH/CRITICAL backlog is triaged.
- `aquasecurity/trivy-action` tags carry a `v` prefix (`@v0.36.0`) — the bare form does not resolve.

---

## 📋 Week 6 (original): UI & Demo - SUPERSEDED

Original goals (production UI + demo video + elevator pitch) were absorbed into Week 3's Telegram pivot. This slot is now Week 6 = Deployment.

**Goals (legacy reference):**
- Production-ready UI
- Demo video
- Elevator pitch

**High-Level Tasks:**
1. UI polish and animations
2. Error handling improvements
3. Demo script writing
4. Video recording
5. Deployment (optional)

---

## 📋 Week 7: Documentation & Delivery (May 3-9) - UPCOMING

**Goals:**
- Complete documentation
- Code cleanup
- Final submission

**High-Level Tasks:**
1. Comprehensive README
2. Code comments and docstrings
3. Setup instructions
4. requirements.txt finalization
5. Final testing

---

## Development Metrics

### Code Quality
- Test Coverage: Target >80%
- Type Hints: 100% of public functions
- Docstrings: 100% of public functions
- Linting: Zero errors (black, flake8)

### Git Stats
- Total Commits: [Auto-updated]
- Open PRs: [Auto-updated]
- Merged PRs: [Auto-updated]

### Time Tracking
- Week 1: [Hours spent]
- Week 2: [Hours spent]
- Week 3: [Hours spent]
- Total: [Hours spent]

---

## Engineering Decisions Log

### Decision 1: Database Choice
**Date:** Week 1  
**Decision:** Use SQLite  
**Reasoning:** Lightweight, no server setup, sufficient for prototype  
**Alternatives Considered:** PostgreSQL (overkill for MVP)

### Decision 2: Web Framework
**Date:** Week 2  
**Decision:** Flask  
**Reasoning:** Simple, lightweight, fast to prototype  
**Alternatives Considered:** FastAPI (more complex for our needs)

### Decision 3: Frontend Approach
**Date:** Week 3  
**Decision:** HTML/CSS/JS (vanilla)  
**Reasoning:** Keep it simple, upgrade to React in Week 6 if time permits  
**Alternatives Considered:** React from start (premature optimization)

### Decision 4: AI Model Selection
**Date:** Week 2  
**Decision:** Claude Sonnet 4  
**Reasoning:** Best cost/performance, good for prototype  
**Alternatives Considered:** GPT-4 (more expensive), Haiku (less capable)

---

## Blockers & Issues

### Active Blockers
*None currently*

### Resolved Issues
1. **Gmail API quota limits** - Resolved by implementing caching
2. **OAuth token expiration** - Resolved with automatic refresh

---

## Next Actions

**Immediate Next Steps (Week 3):**
1. Break Week 3 into 7 specific tasks ✅ (done above)
2. Set up GitHub Actions CI/CD
3. Start Task 1: Draft Reply Generation
4. Create first PR
5. Merge and move to Task 2

**How to Continue:**
```bash
claude "Start Week 3 Task 1: Draft Reply Generation. Create feature branch and implement with tests."
```

---

**Last Updated:** 2026-05-29  
**Current Focus:** Week 5 (Agentic) + Week 6-C (observability); QA hardening pass complete (incl. follow-up agent fix)
