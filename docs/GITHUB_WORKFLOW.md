# GitHub Workflow - Email Assistant Project

**Purpose:** Professional Git workflow with PRs, CI, and ticket management for the email assistant project.

---

## Tooling Standard

Use these tools correctly:

| Tool | Use for | Never use for |
|------|---------|---------------|
| `git` | Commits, branches, push/pull | Creating GitHub issues or PRs |
| `gh` CLI | GitHub issues, PRs, CI checks | Pushing code (use `git push`) |

**Setup once:**
```bash
gh auth setup-git
```

---

## Development Workflow

### 1. Start a New Task

From `docs/PROGRESS.md`, pick the next task (e.g., Week 3 Task 1).

**Create GitHub Issue:**
```bash
gh issue create \
  --title "Week 3 Task 1: Draft Reply Generation" \
  --label "user-story,size:M,priority:high,area:ai" \
  --body "$(cat <<'EOF'
## User Story

**As a** user,
**I want** AI to generate draft email replies in 3 different tones,
**So that** I can quickly respond to emails with appropriate formality.

## Context

Part of Week 3 - Core Chat Logic. This implements the core AI reply generation feature.

See: [`docs/PRD.md#week-3`](docs/PRD.md#week-3)

## Acceptance Criteria

- [ ] Can generate professional tone reply
- [ ] Can generate friendly tone reply  
- [ ] Can generate brief tone reply
- [ ] Drafts stored in database
- [ ] All functions have type hints
- [ ] >80% test coverage

## Test Scenarios

| Scenario | Given | When | Then |
|---|---|---|---|
| Generate professional reply | Email asking for meeting | Request professional tone | Returns formal reply with proper greeting |
| Generate friendly reply | Casual email from colleague | Request friendly tone | Returns warm, conversational reply |
| Generate brief reply | Simple yes/no question | Request brief tone | Returns <3 sentence reply |

## Sub-Tasks

### Backend (BE)
- [ ] Create `src/ai/reply_generator.py`
- [ ] Add `generate_replies()` function with 3 tone options
- [ ] Implement prompt templates for each tone
- [ ] Add database methods for storing drafts
- [ ] Add type hints to all functions

### QA
- [ ] Write unit tests for each tone
- [ ] Test with real email samples
- [ ] Verify database storage
- [ ] Check test coverage >80%
EOF
)"
```

**Note the issue number** (e.g., `#5`)

### 2. Create Feature Branch

```bash
git checkout -b feature/draft-reply-generation
```

### 3. Implement the Feature

Work on the code following the sub-tasks from the issue.

### 4. Run Tests Locally

```bash
# Run tests
pytest tests/ -v --cov=src --cov-report=term

# Run linting
black src/ tests/
flake8 src/ tests/ --max-line-length=100
```

### 5. Commit Your Work

```bash
git add .
git commit -m "feat: implement draft reply generation with 3 tones

- Add reply_generator.py with professional/friendly/brief tones
- Add prompt templates for each tone
- Store drafts in database
- Add unit tests with 85% coverage

Closes #5"
```

**Commit Message Format:**
```
<type>: <short description>

<detailed description>
<bullet points of changes>

Closes #<issue-number>
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

### 6. Create Pull Request

```bash
# Push branch
git push -u origin feature/draft-reply-generation

# Create PR
gh pr create \
  --title "Week 3 Task 1: Draft Reply Generation" \
  --body "$(cat <<'EOF'
Closes #5

## Summary
- Implements AI-powered reply generation with 3 tones
- Adds database storage for drafts
- Includes comprehensive test suite

## Changes
- `src/ai/reply_generator.py` - New module with tone-based generation
- `src/database/db.py` - Add draft storage methods
- `tests/test_reply_generator.py` - Unit tests (85% coverage)

## Test Plan
- [x] All tests pass locally
- [x] Linting clean (black, flake8)
- [x] Type hints on all functions
- [x] Coverage >80%
- [x] Manual testing with real emails

## Acceptance Criteria from #5
- [x] Can generate professional tone reply
- [x] Can generate friendly tone reply  
- [x] Can generate brief tone reply
- [x] Drafts stored in database
- [x] All functions have type hints
- [x] >80% test coverage
EOF
)"
```

### 7. Monitor CI

```bash
# Check CI status
gh pr checks

# If CI fails, fix and push again:
# (make fixes)
git add .
git commit -m "fix: address CI failures"
git push

# CI will re-run automatically
```

### 8. After PR Merges

**Link PR to Issue:**
```bash
gh issue comment 5 --body "PR: #<PR-number>"
```

**Update Issue Checkboxes:**
```bash
# Read current issue body
gh issue view 5 --json body --jq '.body' > issue_body.txt

# Edit it to check off completed criteria
# Change `- [ ]` to `- [x]` for completed items
# Then update:
gh issue edit 5 --body "$(cat issue_body.txt)"
```

**Post Completion Comment:**
```bash
gh issue comment 5 --body "## ✅ Task Complete

**Status:** Merged
**PR:** #<PR-number>
**Test Coverage:** 85%
**Duration:** 4 hours

All acceptance criteria met. Moving to Week 3 Task 2."
```

**Close Issue:**
```bash
gh issue close 5 --reason completed
```

**Update PROGRESS.md:**
```bash
# Update docs/PROGRESS.md to mark task complete
# Change status from 🔲 to ✅
git checkout main
git pull
# Edit PROGRESS.md
git add docs/PROGRESS.md
git commit -m "docs: mark Week 3 Task 1 complete"
git push
```

---

## CI/CD Pipeline

Your `.github/workflows/tests.yml` and `.github/workflows/lint.yml` run automatically on every PR.

**What happens:**
1. Push to PR branch → CI triggers
2. Tests run (pytest)
3. Linting runs (black, flake8)
4. Type checking runs (mypy)
5. Coverage check (must be >80%)

**If CI fails:**
- Check the logs: `gh pr checks <PR-number> --watch`
- Fix the issue locally
- Push again → CI re-runs

**If CI passes:**
- Merge the PR (manually or set up auto-merge)
- Follow post-merge steps above

---

## Quick Reference

### Common Commands

```bash
# List open issues
gh issue list --state open

# View an issue
gh issue view <number>

# Create issue from template
gh issue create --template user-story.md

# Check PR status
gh pr view <number>

# Check CI status
gh pr checks <number>

# View PR diff
gh pr diff <number>

# Merge PR (after CI passes)
gh pr merge <number> --squash --delete-branch

# Close issue
gh issue close <number> --reason completed
```

### Project-Specific Patterns

**For each Week 3-7 task:**
1. Create GitHub issue with acceptance criteria
2. Create feature branch
3. Implement → Test → Commit
4. Push → Create PR
5. Monitor CI → Fix if needed
6. After merge → Update issue → Close

**For bugs:**
1. Create bug issue with reproduction steps
2. Same PR workflow as features
3. Add regression tests

---

## Integration with Claude Code

**Tell Claude Code to follow this workflow:**

```bash
claude "
I want you to follow docs/GITHUB_WORKFLOW.md for all development.

For each task:
1. Create a GitHub issue with this command
2. Create feature branch
3. Implement the feature
4. Create PR following the format
5. After merge, close the issue

Start with Week 3 Task 1. Create the GitHub issue first.
"
```

---

## Tips

✅ **Do:**
- Create issues before starting work
- Use descriptive branch names
- Write clear commit messages
- Keep PRs small and focused
- Update issue checkboxes after completion

❌ **Don't:**
- Push directly to main
- Create PRs without issues
- Merge failing CI
- Leave issues open after merge
- Forget to update PROGRESS.md

---

**Last Updated:** Week 3
