# User Story Template

Use this template when creating feature issues for the email assistant project.

---

## Title
[Imperative mood: "Add user authentication", not "Adding..."]

## Labels
- `user-story`
- `size:S` or `size:M` or `size:L` or `size:XL`
- `priority:critical` or `priority:high` or `priority:medium` or `priority:low`
- `area:api` or `area:frontend` or `area:ai` or `area:database` or `area:cli`

## Body

```markdown
## User Story

**As a** [role],
**I want** [capability],
**So that** [benefit].

## Context

[1-3 sentences explaining why this story exists now. Link to relevant docs.]

See: [`docs/PRD.md#section`](docs/PRD.md#section) | [`docs/PROGRESS.md#week-N`](docs/PROGRESS.md#week-N)

## Acceptance Criteria

- [ ] [Concrete, binary pass/fail condition]
- [ ] [Another criterion]
- [ ] [Another criterion]
- [ ] All functions have type hints
- [ ] >80% test coverage

## Test Scenarios

| Scenario | Given | When | Then |
|---|---|---|---|
| [Happy path] | [precondition] | [action] | [expected result] |
| [Edge case] | [precondition] | [action] | [expected result] |
| [Error case] | [precondition] | [action] | [expected result] |

## Technical Notes

[Optional - only if there are specific implementation constraints]

- [Relevant architecture decision]
- [API contract or data model notes]

## Sub-Tasks

### Backend (BE)
- [ ] [Specific backend task]
- [ ] [Another task]

### Frontend (FE)
- [ ] [Specific frontend task]

### Integration
- [ ] [Integration task if needed]

### QA
- [ ] [Test implementation task]
- [ ] [Coverage verification]
```

---

## Example: Week 3 Task 1

```markdown
## User Story

**As a** user,
**I want** AI to generate draft email replies in 3 different tones,
**So that** I can quickly respond with appropriate formality.

## Context

Week 3 core feature - implements AI reply generation which is central to the email assistant value proposition.

See: [`docs/PRD.md#feature-3-smart-reply-generation`](docs/PRD.md#feature-3-smart-reply-generation)

## Acceptance Criteria

- [ ] Can generate professional tone reply
- [ ] Can generate friendly tone reply
- [ ] Can generate brief tone reply
- [ ] Drafts stored in database with tone label
- [ ] All functions have type hints
- [ ] >80% test coverage

## Test Scenarios

| Scenario | Given | When | Then |
|---|---|---|---|
| Professional reply | Formal meeting request email | Request professional tone | Returns formal reply with proper salutation |
| Friendly reply | Casual message from colleague | Request friendly tone | Returns warm, conversational reply |
| Brief reply | Simple yes/no question | Request brief tone | Returns reply under 3 sentences |
| Thread context | Email is part of 5-message thread | Generate any tone | Reply references previous context |

## Technical Notes

- Use Claude Sonnet 4 API (best cost/performance)
- Implement prompt caching to save 90% on repeated template tokens
- Store tone as enum: PROFESSIONAL, FRIENDLY, BRIEF

## Sub-Tasks

### Backend (BE)
- [ ] Create `src/ai/reply_generator.py`
- [ ] Implement `generate_replies(email_data, tones=['professional', 'friendly', 'brief'])`
- [ ] Add prompt templates in `src/ai/prompt_templates.py`
- [ ] Extend `src/database/db.py` with `insert_draft_reply()` and `get_drafts_for_email()`
- [ ] Add type hints to all functions

### QA
- [ ] Write `tests/test_reply_generator.py` with tests for each tone
- [ ] Test with real Gmail API data (use test account)
- [ ] Verify database storage and retrieval
- [ ] Measure and verify >80% code coverage
- [ ] Performance test: <2 seconds per reply generation
```
