# Sprint Reports - Email Assistant Project

Track weekly progress, metrics, and retrospectives.

---

## Week 3: Telegram Integration + Draft Replies (Apr 5 – May 5, 2026)

**Status:** ✅ Complete — all four stories shipped, Email Copilot fully driven from Telegram.

### Planned Tasks (post 2026-04-24 Telegram pivot)
- [x] Story A: Telegram bot scaffolding + webhook + auth — PR #14
- [x] Story B: Pull commands `/unread`, `/analyze`, `/inbox` — PR #16
- [x] Story C: Draft reply generation + approve-before-send flow — PR #19
- [x] Story D: Push notifications for high-priority emails — PR #21

### Bootstrap shipped during Week 3
- [x] CI/CD (`tests.yml`, `lint.yml`) — PR #10 (2026-04-23)
- [x] REST API pipeline (kept for backend testing) — PR #8
- [x] Integration test scaffold + shared fixtures — PR #17 (2026-05-04)
- [x] Professional workflow docs + PR template + sprint reports — `733692d` (2026-05-04)

### Metrics
- **PRs Merged:** 6 in Week 3 (#14, #16, #17, #19, #21, plus bootstrap CI in #10)
- **Test Coverage:** **91.94%** (gate 80%); test count grew 62 → 131 over the week.
- **CI Success Rate:** 100% — every PR submitted went green on first push.
- **Average PR Size:** ~600 LoC; #19 was the outlier at 1,326 LoC (Story C bundled DB + AI + Gmail + Telegram).
- **Stories per week:** 4 user stories + scaffolding work = full sprint plan delivered on schedule.

### Completed This Week
1. Story C — `/reply <id>` flow with 3-tone drafts, inline keyboard (Approve / Edit / Skip / Regenerate), `ConversationHandler`-driven Edit, Gmail send with `In-Reply-To` + `References` threading. Closed #18 in PR #19.
2. Story D — APScheduler-driven background job, `notified_at` idempotency gate, `format_notification` MarkdownV2 block, Generate Reply (reuses Story C) + Mark Done buttons, `/pause` and `/resume` commands. Closed #20 in PR #21.
3. Professional workflow scaffolding — `docs/PROFESSIONAL_WORKFLOW.md`, `docs/SPRINT_REPORTS.md`, `.github/PULL_REQUEST_TEMPLATE.md`. Commit `733692d`.

### Challenges
- `draft_replies` table existed pre-Story C with only `was_sent`. Resolved with a non-destructive `ALTER TABLE` migration in `init_db()` so existing local DBs gain the new `status` column without manual `rm email_assistant.db`. Same pattern reused for `emails.notified_at` in Story D.
- Telegram `ConversationHandler` is hard to unit-test as a whole; covered the trivial cancel/timeout callbacks directly and trusted the wiring via integration use.
- APScheduler's `AsyncIOScheduler.start()` requires a running event loop, which broke the first lifecycle test. Fixed by switching the test to `@pytest.mark.asyncio` so pytest-asyncio's loop is active.

### Lessons Learned
**What went well**
- One feature → one issue → one PR → one merge held across all four stories. Acceptance criteria from issue bodies mapped 1:1 to PR test scenarios, which cut review thinking to almost zero.
- Pre-push trio (`black`, `flake8`, `pytest --cov`) caught every formatting + lint nit before CI; CI is a confirmation step, never a debug step.
- Story D's "Generate Reply" button reused Story C's `reply_command` directly — no duplicated logic. The investment in clean Story C boundaries paid off when Story D needed an entry point.
- Idempotency-via-DB-column (`notified_at`) is much simpler than tracking state in scheduler memory; survives restarts for free.

**What to improve**
- Story C's PR was 1,326 LoC. Future L stories should still ship as one PR but split into two commits (foundation: DB + helpers; flow: handlers + UI) so reviewers can read incrementally.
- Black reformatting on first push is noise — add `black` to a pre-commit hook so it runs locally without an explicit invocation.
- The "Generate Reply" callback mutates `update.message = query.message` to delegate to `reply_command`. It works, but a third entry point should trigger a refactor to a `_handle_reply(chat_id, email_id, message)` core.

### Next Week Preview
- **Week 4 — External Data + Knowledge:** Calendar API integration, meeting detection in emails, natural-language date parsing, calendar event creation. PRD has the spec; need to break it into 2–3 stories sized like Week 3.
- Open question: do we add a Telegram `/calendar` command up front, or surface meeting events as auto-detected during the existing analyze flow? Decide during sprint planning.

---

## Week 2: Integration POC + System Design (Mar 22-28, 2026)

**Status:** ✅ Complete

### Completed Tasks
- [x] Database schema designed
- [x] SQLite setup working
- [x] Email fetching (10 unread)
- [x] Claude API integrated
- [x] AI analysis functional
- [x] System architecture documented

### Metrics
- **Test Coverage:** ~60% (need improvement)
- **Features Delivered:** 5/5
- **Code Quality:** Good (manual review)

### Lessons Learned
- Database design took longer than expected
- Claude API integration smoother than anticipated
- Need to add integration tests earlier

### What Went Well
- All planned features completed
- Good progress on infrastructure
- Documentation kept up-to-date

### What to Improve
- Start writing tests earlier (not at the end)
- Better time estimates for database work
- Add CI checks earlier in the week

---

## Week 1: Setup & Project Definition (Mar 15-21, 2026)

**Status:** ✅ Complete

### Completed Tasks
- [x] Development environment setup
- [x] Gmail API credentials obtained
- [x] OAuth 2.0 working
- [x] Can fetch emails
- [x] Project structure created
- [x] Git repository initialized

### Metrics
- **Setup Time:** ~8 hours
- **Blockers:** 1 (Gmail API quota issue, resolved)
- **Documentation:** Complete (PRD, PROGRESS, README)

### Lessons Learned
- Gmail API setup documentation excellent
- OAuth flow more complex than expected
- Good foundation saves time later

### What Went Well
- Clean project structure from start
- Documentation created early
- No major blockers

### What to Improve
- Could have parallelized some setup tasks
- Should have researched OAuth earlier

---

## Sprint Report Template (Copy for each week)

```markdown
## Week N: [Phase Name] ([Dates])

**Status:** In Progress / Complete

### Planned Tasks
- [ ] Task 1: Description
- [ ] Task 2: Description
- [ ] Task 3: Description

### Metrics
- **PRs Created:** X
- **PRs Merged:** X
- **Test Coverage:** X%
- **CI Success Rate:** X%
- **Average PR Size:** X lines
- **Average PR Merge Time:** X hours

### Completed This Week
1. Feature/Task 1 - PR #X
2. Feature/Task 2 - PR #Y
3. Bug Fix - PR #Z

### Challenges
- Challenge 1: Description and how resolved
- Challenge 2: Description and status

### Lessons Learned
**What went well:**
- Thing 1
- Thing 2

**What to improve:**
- Thing 1
- Thing 2

**Technical insights:**
- Insight 1
- Insight 2

### Next Week Preview
- Task 1
- Task 2
- Focus area
```

---

## Overall Project Metrics (Cumulative)

**As of Week 3:**
- **Total PRs Merged:** TBD
- **Total Issues Closed:** TBD
- **Average Test Coverage:** TBD
- **Total Lines of Code:** TBD
- **Total Tests Written:** TBD
- **CI Success Rate:** TBD
- **Features Completed:** X/Y

**Code Quality:**
- Lint Errors: 0 (target)
- Type Hint Coverage: TBD%
- Documentation: TBD pages

**Velocity:**
- Tasks per week: TBD
- Average task time: TBD hours
- On schedule: Yes/No

---

## Retrospective Notes

### Most Valuable Practices
*Update as you discover what works*

### Process Improvements
*Document workflow improvements over time*

### Technical Decisions
*Log major technical decisions and their outcomes*

---

**Last Updated:** Week 3
