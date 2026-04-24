---
name: pr-workflow
description: Push a feature/fix branch, open a PR, monitor CI, and run the full post-merge sequence (link PR ↔ issue, tick acceptance criteria, post completion report, close issue) for the AI Email Copilot project. Use when you've finished implementing a ticket and need to ship it. Pairs with the `github`, `create-user-story`, and `create-bug` skills.
---

# PR Workflow

Handle the GitHub side of shipping a ticket: push, open PR, watch CI, merge, close. This skill is the operational counterpart to `create-user-story` / `create-bug` (which open the ticket) and `github` (which defines tooling rules).

## Identify the Repository

```bash
git remote get-url origin
```

Parse `owner/repo` from the URL. Never hardcode.

## Operations

### 1. Pre-Push Local Verification

Mirror CI before pushing — failing checks waste a CI run:

```bash
.venv/Scripts/black app/ tests/
.venv/Scripts/flake8 app/ tests/
.venv/Scripts/pytest tests/ --cov=app --cov-report=term
```

All three must be green. Coverage must be ≥80% (enforced by `pyproject.toml`).

### 2. Push the Branch

Branch names: `feature/<short-kebab>` for stories, `fix/<short-kebab>` for bugs.

```bash
git push -u origin <branch-name>
```

### 3. Open the PR

The PR body **must** contain `Closes #<N>` so the issue auto-closes on merge. Use a HEREDOC for clean multi-line bodies.

```bash
gh pr create --title "<title>" --body "$(cat <<'EOF'
Closes #<ticket-number>

## Summary
- <bullet 1 — what changed and why>
- <bullet 2>
- <bullet 3>

## Changes
- `app/<module>.py` — <what>
- `tests/unit/test_<module>.py` — <what>

## Test Plan
- [x] `pytest tests/ --cov=app` passes (X tests, Y% coverage)
- [x] `black app/ tests/` clean
- [x] `flake8 app/ tests/` clean
- [x] Manual verification: <how you confirmed the fix/feature works end-to-end>

## Acceptance Criteria from #<N>
- [x] <criterion 1>
- [x] <criterion 2>
- [x] <criterion 3>
EOF
)"
```

Capture the returned PR number.

### 4. Link PR ↔ Issue

`Closes #N` already creates a soft link. Add an explicit comment for visibility:

```bash
gh issue comment <ticket-number> --body "PR: #<PR-number>"
```

### 5. Monitor CI

```bash
gh pr checks <PR-number> --watch
```

- **CI fails:** pull the failure logs (`gh run view <RUN-ID> --log-failed`), fix the root cause on the branch, push again. CI re-triggers automatically. Don't silence failures with `# noqa` or `# pragma: no cover` unless there's a real reason (e.g., live-OAuth path that can't be unit-tested).
- **CI passes:** proceed to merge. This project does **not** have auto-merge configured — merge manually.

### 6. Merge

```bash
gh pr merge <PR-number> --squash --delete-branch
```

Squash-merge keeps `main` history clean (one commit per ticket). The `--delete-branch` flag cleans up the remote branch.

### 7. Update Acceptance Criteria

Even though the PR body listed them as checked, the issue body still has unchecked boxes. Sync them:

```bash
gh issue view <ticket-number> --json body --jq '.body' > /tmp/issue_body.md
# Edit /tmp/issue_body.md, change [ ] → [x] for satisfied criteria
gh issue edit <ticket-number> --body "$(cat /tmp/issue_body.md)"
```

### 8. Post Completion Report

```bash
gh issue comment <ticket-number> --body "$(cat <<'EOF'
## ✅ Task Complete

**Status:** Merged
**PR:** #<PR-number>
**Commit:** <merge SHA>
**Tests:** <N> passing | **Coverage:** <X>%
**Lint:** black + flake8 clean

All acceptance criteria met. Moving to <next task per docs/PROGRESS.md>.
EOF
)"
```

### 9. Close the Issue

`Closes #N` in the PR body auto-closes the issue on merge — but verify, and close manually if it didn't:

```bash
gh issue view <ticket-number> --json state --jq '.state'
# If still "OPEN":
gh issue close <ticket-number> --reason completed
```

### 10. Update PROGRESS.md

```bash
git checkout main
git pull
# Edit docs/PROGRESS.md — flip the task status from 🔲 → ✅
git add docs/PROGRESS.md
git commit -m "docs: mark <Week N Task M> complete"
git push
```

## Rules

- **`git` for code, `gh` for platform.** Never use MCP `push_files` for code (per `.claude/skills/github.md`).
- **Always derive `owner/repo` from `git remote`.** Never hardcode.
- **Pre-push verification is mandatory.** A CI failure on something black would have fixed locally is wasted time.
- **Autonomous post-PR execution.** After creating the PR, run steps 5–10 without asking. Pause only on:
  - Genuine CI failures you can't diagnose from the logs alone
  - Acceptance criteria that are *not* satisfied (don't lie by ticking them)
  - Merge conflicts that need user judgment on resolution
- **Never skip steps 7–10 silently.** A merged PR with an open issue and stale `PROGRESS.md` is a process bug.
- **Don't bypass hooks** (`--no-verify`) or signing. If a hook fails, fix the underlying issue.