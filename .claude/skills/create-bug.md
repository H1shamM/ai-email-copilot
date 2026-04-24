---
name: create-bug
description: Create a structured bug report (GitHub issue) for the AI Email Copilot project with reproduction steps, expected/actual results, environment details, affected components, severity assessment, and fix sub-tasks. Use when the user reports a bug, says things like "there's a bug in...", "X is broken", "this isn't working right", "file a bug for...", or describes any defect that needs tracking. One bug at a time.
---

# Create Bug Report

Create a well-structured GitHub issue that gives the implementer everything needed to reproduce, diagnose, and fix the defect. Mirror `docs/BUG_REPORT_TEMPLATE.md` and create the issue via `gh` per `.claude/skills/github.md`.

## Step 1: Gather Context

1. **Understand the bug.** Extract what's broken. If vague, ask focused questions — one round max:
   - What were they doing when it happened?
   - Expected vs actual behavior?
   - Reproducible consistently or intermittent?
   - Any error messages, logs, screenshots?

2. **Identify affected components.** Use Grep/Glob to trace from symptom to likely cause. Map to this project's layers:

   | Layer | Files |
   |---|---|
   | **API / FastAPI endpoints** | `app/main.py` |
   | **Gmail / OAuth** | `app/gmail/auth.py`, `app/gmail/service.py` |
   | **Claude / AI** | `app/ai/analyzer.py` |
   | **Data layer (SQLite)** | `app/database/db.py` |
   | **Schemas / validation** | `app/models/schemas.py` |
   | **Config / env** | `.env`, `pyproject.toml` |
   | **CI / tooling** | `.github/workflows/`, `.flake8`, `requirements*.txt` |
   | **Tests** | `tests/unit/`, `tests/integration/`, `tests/conftest.py` |

3. **Scan docs for intended behavior.** Search `docs/PRD.md` and `docs/PROGRESS.md` for the feature spec. A "bug" might be unimplemented behavior — flag it as a missing-feature story instead if so.

4. **Assess severity:**

   | Severity | Criteria |
   |---|---|
   | **critical** | App won't start, data loss, secret leak, no workaround |
   | **high** | Core flow broken (fetch / analyze / reply), workaround painful |
   | **medium** | Non-core feature broken, reasonable workaround exists |
   | **low** | Cosmetic, edge case, minimal impact |

   Ask the user if not obvious.

## Step 2: Investigate Before Writing

Provide value beyond transcribing the user's complaint:

- **Trace the code path** — entry point → where the bug manifests. Note files and line numbers.
- **Check related patterns** — TODOs, similar bugs, known limitations.
- **Identify likely root cause** — even narrowing to one module saves the fixer time.
- **Check test coverage** — is there a test for this code path? If so, why didn't it catch it? That's a sub-task.

## Step 3: Write the Report

Mirror `docs/BUG_REPORT_TEMPLATE.md`. Omit sections that don't apply.

```markdown
## Bug Summary

[1-2 sentences. Be specific — "X returns Y when it should return Z", not "X doesn't work".]

## Environment

| Field | Value |
|---|---|
| Version / Commit | [git SHA from `git rev-parse HEAD`, or "main as of YYYY-MM-DD"] |
| OS / Platform | [e.g., Windows 11, macOS 15] |
| Python Version | [e.g., 3.14.0 — check `.venv/Scripts/python --version`] |
| Deployment | [local uvicorn / Docker / CI] |
| Configuration | [relevant env vars from `.env` — never paste actual API keys] |

## Components Affected

- **Primary:** [`app/<module>.py`](app/<module>.py) — [what it does]
- **Secondary:** [`app/<other>.py`](app/<other>.py) — [how it's involved]

## Reproduction Steps

1. [Exact first step — commands, inputs, curl calls, UI actions]
2. [Next step]
3. [Step where the bug manifests]

**Reproduction rate:** [Always / Intermittent (~X%) / One-time]

## Expected Result

[Concrete: expected output, status code, JSON shape, behavior. Reference PRD if applicable.]

## Actual Result

[Concrete: exact error message, wrong output, observed behavior.]

## Evidence

<details>
<summary>Error output / Stack trace</summary>

\`\`\`
[Raw error output — never paraphrase]
\`\`\`

</details>

<!-- Only if logs exist -->
<details>
<summary>Relevant logs</summary>

\`\`\`
[uvicorn output, pytest output, etc.]
\`\`\`

</details>

## Root Cause Analysis

<!-- Only if narrowed down — even partial is valuable -->

**Likely cause:** [File path + line number + what's wrong at code level]

**What's been ruled out:** [Things checked that are NOT the cause — saves duplicate investigation]

## Acceptance Criteria (Definition of Fixed)

- [ ] [Specific condition true when fixed]
- [ ] No regression in [related functionality from PRD]
- [ ] All existing tests still pass (`pytest tests/ --cov=app`)
- [ ] Coverage stays ≥80%
- [ ] `black` and `flake8` clean

## Regression Test Scenarios

| Scenario | Given | When | Then |
|---|---|---|---|
| [Original bug] | [precondition] | [trigger action] | [correct result] |
| [Boundary case] | [related precondition] | [similar action] | [expected result] |
| [Previously working case] | [precondition] | [should-still-work action] | [unchanged result] |

<!-- Only if real architectural constraints -->
## Technical Notes

- [Engineering Decision from `docs/PROGRESS.md` that constrains the fix]
- [Related code pattern or known limitation]

<!-- Only if related issues exist -->
## Related Issues

- Related to: #[N] — [relationship]
```

### Writing Rules

- Reproduction steps must be precise enough for someone unfamiliar with the code to follow.
- Expected/actual must be concrete — not "should work" but "should return `{"analyzed": 50}` with HTTP 200".
- Evidence is **raw** — no paraphrasing of stack traces.
- Never paste secrets (`ANTHROPIC_API_KEY`, OAuth tokens). Redact or describe.
- Link to specific files and line numbers (`app/main.py:62`).

## Step 4: Sub-Task Breakdown

Almost every bug needs a fix + a regression test. The QA category is rarely empty.

```markdown
## Sub-Tasks

### BE
- [ ] [Specific fix — file path + what changes]
- [ ] [Defensive check or refactor needed alongside fix]

### Integration
- [ ] [If bug crosses module boundaries — e.g., Gmail → DB pipeline]

### QA
- [ ] Add regression test in `tests/unit/test_<module>.py` covering the original scenario
- [ ] Add boundary-case test
- [ ] Verify `pytest tests/ --cov=app` stays ≥80% and all tests pass
```

Each sub-task must be:
- **Actionable** — implementer can start without further clarification
- **Traceable** — references file paths, function names, or line numbers
- **Ordered** — fix first, then regression tests, then verification

## Step 5: Pick Labels

Per `docs/BUG_REPORT_TEMPLATE.md`:

| Label | How to pick |
|---|---|
| `bug` | Always |
| `severity:critical` / `high` / `medium` / `low` | From the severity matrix above |
| `priority:critical` / `high` / `medium` / `low` | Business urgency. Often = severity, but ask if they differ. |
| Area: `area:api`, `area:frontend`, `area:ai`, `area:database`, `area:cli` | From the primary affected module |

## Step 6: Present and Confirm

Show the complete report (title + labels + body + sub-tasks) to the user. Ask: "Ready to file this, or want changes?"

Iterate.

## Step 7: Create the Issue

After approval, use `gh` (per `.claude/skills/github.md` — never MCP `push_files`):

```bash
gh issue create \
  --title "[<Component>] <description>" \
  --label "bug,severity:high,priority:high,area:ai" \
  --body "$(cat <<'EOF'
<full body + sub-tasks>
EOF
)"
```

Capture the issue number — the fixer needs it for the branch (`fix/<short-kebab-name>`) and the commit `Closes #N`.