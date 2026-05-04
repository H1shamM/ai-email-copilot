## Summary

<!-- One or two sentences. What changed and why. -->

Closes #<!-- issue number -->

## Changes

<!-- Bullet list of the meaningful changes. Group by area when helpful. -->

-
-
-

## How to test

<!-- Steps a reviewer can run locally to verify the change. -->

```bash
.venv/Scripts/black --check app/ tests/
.venv/Scripts/flake8 app/ tests/
.venv/Scripts/pytest tests/ --cov=app
```

- [ ] Unit tests added/updated under `tests/unit/`
- [ ] Integration test added (only if a new external API boundary was crossed)
- [ ] Manual verification steps:
  -

## Screenshots / sample output

<!-- For UI or Telegram changes, paste a screenshot or formatted message sample. -->

## Checklist

- [ ] PR title follows Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- [ ] Body links the issue with `Closes #<N>`
- [ ] All public functions have type hints (Python 3.10+ syntax: `int | None`, `list[dict]`)
- [ ] All public functions have a one-line docstring
- [ ] No comments restating *what* the code does — only *why* when non-obvious
- [ ] No secrets, tokens, or real credentials committed (verify `.env` / `token.pickle` are gitignored)
- [ ] Coverage ≥ 80% on the changed module(s)
- [ ] `black --check` and `flake8` pass locally
- [ ] CI is green (tests + lint workflows)
- [ ] `docs/PROGRESS.md` updated if a Week-N task is completed
- [ ] `docs/SPRINT_REPORTS.md` updated if this closes the sprint

## Notes for the reviewer

<!-- Optional: highlight tricky areas, open questions, or follow-ups split into other issues. -->
