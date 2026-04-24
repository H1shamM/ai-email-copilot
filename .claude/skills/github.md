---
name: github
description: GitHub platform tooling and CI conventions for the AI Email Copilot project. Use when creating issues, opening PRs, checking CI, or moving code between local and remote.
---

# GitHub Platform Reference

GitHub-specific tooling and CI configuration for this project. For the broader operational workflow (ticket-driven development, branch strategy, PR lifecycle), see [`docs/GITHUB_WORKFLOW.md`](../../docs/GITHUB_WORKFLOW.md).

## Tooling Standard

Two tools, each for its job:

| Tool | Use for | Never use for |
|------|---------|---------------|
| `git` | Push, pull, commit, branch — all code movement | GitHub platform ops (issues, PRs, checks) |
| `gh` CLI | Issues, PRs, checks, releases — all GitHub platform ops | Pushing code (use `git push`) |
| MCP GitHub plugin | Read-only fallback (reading issues, PRs) when `gh` is unavailable | **Pushing code** — `push_files` creates synthetic commits disconnected from local git state |

**Why this matters:** `git push` sends the exact committed objects from your local repo. MCP `push_files` creates a new commit on the server from raw content you provide — if a local linter (black) auto-fixed your files, the API push won't reflect that, causing CI failures on code that passed locally.

**Credentials:** Run `gh auth setup-git` once to make `git` use `gh`'s token. This eliminates credential fragmentation between the two tools.

## CI Pipeline

Two workflows live in `.github/workflows/` and run automatically on every PR to `main` and on push to `main`:

### `tests.yml` — Test + Coverage
- **Setup:** Python 3.11 with pip cache
- **Install:** `pip install -r requirements-dev.txt`
- **Run:** `pytest tests/ --cov=app --cov-report=term --cov-report=xml`
- **Coverage gate:** `fail_under = 80` (enforced via `pyproject.toml`)
- **Artifact:** uploads `coverage.xml`
- **Env:** `ANTHROPIC_API_KEY=dummy-key-for-tests` (analyzer tests use mocked client)

### `lint.yml` — Format + Lint + Type Check
- **Black:** `black --check app/ tests/`
- **Flake8:** `flake8 app/ tests/` (config in `.flake8`, max line 100)
- **Mypy:** `mypy app/ --ignore-missing-imports` (`continue-on-error: true` for now)

If CI fails, fix the issue on the branch and push again — the workflow re-triggers automatically.

## Local Pre-Push Checklist

Mirror the CI locally before pushing:

```bash
.venv/Scripts/black app/ tests/
.venv/Scripts/flake8 app/ tests/
.venv/Scripts/pytest tests/ --cov=app --cov-report=term
```

All three must be green. Coverage must be ≥80%.

## GitHub CLI Quick Reference

### Issue Operations

```bash
gh issue list --state open                            # List open issues
gh issue view <NUMBER>                                # Read an issue
gh issue view <NUMBER> --json body --jq '.body'       # Read body raw (for editing)
gh issue create --title "..." --label "..." --body "..."  # Create issue
gh issue edit <NUMBER> --body "$(cat issue_body.txt)" # Update body (e.g., tick checkboxes)
gh issue comment <NUMBER> --body "..."                # Comment on issue
gh issue close <NUMBER> --reason completed            # Close after merge
```

### PR Operations

```bash
gh pr create --title "..." --body "..."               # Create PR
gh pr view <NUMBER>                                   # PR overview
gh pr checks <NUMBER>                                 # CI status
gh pr checks <NUMBER> --watch                         # Tail CI until done
gh pr diff <NUMBER>                                   # Show diff
gh pr merge <NUMBER> --squash --delete-branch         # Squash-merge & cleanup branch
```

### Linking PR ↔ Issue

```bash
# In the PR body, include `Closes #N` to auto-close the issue on merge.
# Optional explicit linking:
gh issue comment <NUMBER> --body "PR: #<PR-number>"
```

## Branch & Commit Conventions

- **Branch:** `feature/<short-kebab-name>` (e.g., `feature/draft-reply-generation`)
- **Commit format:**
  ```
  <type>: <short description>

  - bullet of change 1
  - bullet of change 2

  Closes #<issue-number>
  ```
- **Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

## Autonomous Bug Fixing

- When given a bug report or failing CI: just fix it. Don't ask for hand-holding.
- Point at logs, errors, failing tests — then resolve the root cause.
- Zero context switching required from the user.
- Go fix failing CI tests without being told how — pull the workflow run logs with `gh run view <RUN-ID> --log-failed`.

## Common Failure Modes

- **Black diff in CI:** run `black app/ tests/` locally and recommit (don't add `# fmt: off`).
- **Flake8 unused-import:** delete the import; never silence with `# noqa` unless there's a real reason (e.g., `app/main.py` `load_dotenv()` ordering uses `# noqa: E402`).
- **Coverage below 80%:** add tests, don't lower `fail_under`. If a function genuinely can't be unit-tested (live OAuth, live Gmail), mark it `# pragma: no cover` and document why in the docstring.
- **Test passes locally, fails in CI:** check `ANTHROPIC_API_KEY` env, Python version drift (CI uses 3.11), or filesystem-path assumptions (Windows vs Linux).