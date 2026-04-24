---
name: create-user-story
description: Create a single INVEST-structured user story (GitHub issue) for the AI Email Copilot project. Includes acceptance criteria, test scenarios, links to PRD/PROGRESS docs, and BE/FE/Integration/QA sub-task breakdown. Use when the user says "create a story for...", "I need a ticket for...", "write a user story for...", or describes a feature that needs to be turned into a structured, trackable issue. One story at a time — for multi-story epics, split into separate calls.
---

# Create User Story

Create a single, well-structured GitHub issue that follows INVEST principles. The output goes through `gh issue create` per the conventions in `.claude/skills/github.md` and uses the template in `docs/USER_STORY_TEMPLATE.md`.

## Step 1: Gather Context

1. **Parse the request.** Extract the feature or change. If vague, ask focused questions — one round max. Don't interrogate.

2. **Scan the project docs.** Use Grep on `docs/` to find sections relevant to the feature:
   - **`docs/PRD.md`** — feature specs, success metrics, prompts, schemas, week-by-week plan
   - **`docs/PROGRESS.md`** — current week, task breakdown, status, engineering decisions
   - **`docs/GITHUB_WORKFLOW.md`** — workflow conventions
   - **`docs/USER_STORY_TEMPLATE.md`** — canonical body template (mirror it, don't reinvent)

   Save the file paths and section anchors — link them in the story's **Context** section.

3. **Determine if Figma is needed.** Most stories in this project are backend (FastAPI endpoints, Claude integration, DB work) and won't need Figma. UI work is HTML/CSS/JS per the PRD.

   **Needs Figma:** new UI screens/pages/dialogs, layout changes, new interactive components.
   **Doesn't:** backend, DB, AI prompts, CI, refactoring, config.

   If UI work and the user hasn't provided a link: ask once.

## Step 2: Apply INVEST (internal check, don't output)

- **Independent** — Deliverable without waiting on other stories? Note explicit dependencies if not.
- **Negotiable** — Goal-oriented (what/why), not prescriptive (exactly how).
- **Valuable** — Tied to a real user/stakeholder benefit. Frame tech debt as the value it unlocks.
- **Estimable** — Enough context to size. If not, propose a spike.
- **Small** — Fits in a few days max. If too big, suggest a split (e.g., "draft generation" → "prompt templates" + "DB storage" + "API endpoint").
- **Testable** — Concrete, binary acceptance criteria. If you can't write them, the story is too vague.

## Step 3: Write the Story Body

Mirror `docs/USER_STORY_TEMPLATE.md`. Omit sections that don't apply rather than leaving them empty.

```markdown
## User Story

**As a** [role],
**I want** [capability],
**So that** [benefit].

## Context

[1-3 sentences explaining why this story exists now and where it fits in the weekly plan.]

See: [`docs/PRD.md#section`](docs/PRD.md#section) | [`docs/PROGRESS.md#week-N`](docs/PROGRESS.md#week-N)

<!-- Only if Figma links provided -->
## Design

| Screen / Component | Figma Link |
|---|---|
| [Name] | [URL] |

## Acceptance Criteria

- [ ] [Concrete, binary pass/fail condition]
- [ ] [Another criterion]
- [ ] All public functions have type hints
- [ ] All public functions have docstrings
- [ ] Test coverage ≥80% (enforced by `pyproject.toml`)
- [ ] `black app/ tests/` and `flake8 app/ tests/` clean

## Test Scenarios

| Scenario | Given | When | Then |
|---|---|---|---|
| [Happy path] | [precondition] | [action] | [expected result] |
| [Edge case] | [precondition] | [action] | [expected result] |
| [Error case] | [precondition] | [action] | [expected result] |

<!-- Only if real architectural constraints exist -->
## Technical Notes

- [Specific file path or module to modify]
- [Relevant Engineering Decision from `docs/PROGRESS.md`]
- [API contract, prompt structure, or DB schema note]

<!-- Only if blocked by other work -->
## Dependencies

- Blocked by: #[issue-number] — [reason]
```

### Writing Rules

- Acceptance criteria are binary — no subjective language ("looks good", "performs well").
- Test scenarios describe **behavior**, not implementation.
- Link doc paths from repo root (`docs/PRD.md#anchor`).
- Default acceptance items (type hints, docstrings, ≥80% coverage, lint-clean) are **always** included — they match the CI gates.
- Don't reference files that don't exist yet — the implementer creates them. Just describe what they should do.

## Step 4: Sub-Task Breakdown

After the user approves the body, split into sub-tasks. Only include categories that apply.

### Backend (BE)
FastAPI endpoints (`app/main.py`), Claude integration (`app/ai/`), Gmail API (`app/gmail/`), DB layer (`app/database/db.py`), Pydantic schemas (`app/models/schemas.py`), prompt templates.

### Frontend (FE)
HTML templates, JS, CSS — per PRD this is vanilla HTML/CSS/JS, no React unless Week 6+ scope.

### Integration
Wiring components end-to-end, connecting Gmail+Claude+DB pipelines, third-party services (Calendar API, etc.).

### QA
Tests beyond developer unit tests: integration tests in `tests/integration/`, E2E flow tests, performance checks. Always reference the test scenarios from the story.

```markdown
## Sub-Tasks

### BE
- [ ] [Specific actionable task]
- [ ] [Another task]

### FE
- [ ] [Specific frontend task]

### Integration
- [ ] [Specific integration task]

### QA
- [ ] [Specific QA task — reference scenarios from above]
```

Each sub-task must be:
- **Actionable** — implementable without further clarification
- **Scoped** — one logical unit of work
- **Ordered** — list in dependency order

## Step 5: Pick Labels

Per `docs/USER_STORY_TEMPLATE.md`:

| Label | How to pick |
|---|---|
| `user-story` | Always |
| `size:S` / `size:M` / `size:L` / `size:XL` | S = hours, M = 1-2 days, L = 3-5 days, XL = needs splitting |
| `priority:critical` / `high` / `medium` / `low` | Match PRD priority (P0=high/critical, P1=medium, P2=low). Ask if unclear. |
| Area: `area:api`, `area:frontend`, `area:ai`, `area:database`, `area:cli` | Derive from BE module touched |

## Step 6: Present and Confirm

Show the **complete** story (title + labels + body + sub-tasks) to the user. Ask: "Ready to create the issue, or want changes?"

Iterate on feedback.

## Step 7: Create the Issue

After approval, create it via `gh` (per `.claude/skills/github.md` — never use MCP `push_files`):

```bash
gh issue create \
  --title "<title>" \
  --label "user-story,size:M,priority:high,area:ai" \
  --body "$(cat <<'EOF'
<full body + sub-tasks>
EOF
)"
```

Capture the returned issue number — the implementer needs it for the branch name (`feature/<short-kebab-name>`) and the commit `Closes #N`.