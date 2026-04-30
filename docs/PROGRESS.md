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

## 🔄 Week 3: Telegram Integration + Draft Replies (Apr 5-11) - IN PROGRESS

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
**Status:** 🔲 Not Started
**Size:** M
**Scope:**
- `/unread` — fetch + return numbered list with sender/subject/snippet
- `/analyze` — run Claude on unprocessed emails, return per-email category/priority/summary
- `/inbox` — last N analyzed emails from DB with priority indicators
- `app/telegram/formatting.py` — MarkdownV2 escaping, 4096-char chunking

---

#### Story C: Draft reply generation + approve-before-send (subsumes original Task 1)
**Branch:** `feature/telegram-reply-flow`
**Status:** 🔲 Not Started
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
**Status:** 🔲 Not Started
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
- [ ] `/unread` and `/analyze` return formatted email summaries in Telegram (Story B)
- [ ] `/reply <id>` flow generates 3 drafts and sends via Gmail after approval (Story C)
- [ ] Bot proactively notifies on priority ≥ 4 emails (Story D)
- [ ] Coverage stays ≥80%
- [ ] CI green on every PR

**Deliverable:** 🎯 Email Copilot fully driven from Telegram

---

## 📋 Week 4: External Data + Knowledge (Apr 12-18) - UPCOMING

**Goals:**
- Calendar integration
- Meeting detection
- Event creation

**High-Level Tasks:**
1. Google Calendar API integration
2. Meeting detection with Claude
3. Natural language date parsing
4. Calendar event creation
5. UI for calendar features

---

## 📋 Week 5: Agentic Workflows (Apr 19-25) - UPCOMING

**Goals:**
- Autonomous decision-making
- Follow-up tracking
- Smart bulk actions

**High-Level Tasks:**
1. Decision agent implementation
2. Priority scoring system
3. Follow-up tracking
4. Reminder system
5. Bulk action handlers

---

## 📋 Week 6: UI & Demo (Apr 26-May 2) - UPCOMING

**Goals:**
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

**Last Updated:** [Date]  
**Current Focus:** Week 3 - Core Chat Logic
