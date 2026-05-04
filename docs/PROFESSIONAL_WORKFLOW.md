# Professional Development Workflow - Email Assistant

**Goal:** Simulate professional software engineering practices used at companies like Google, Meta, Amazon, and Microsoft.

---

## Overview

This project demonstrates professional engineering workflows:
- ✅ Sprint planning with GitHub Issues
- ✅ Feature branches and Pull Requests
- ✅ Continuous Integration (CI)
- ✅ Code review process
- ✅ Automated testing and quality gates
- ✅ Continuous Deployment (CD) - Week 6
- ✅ Production monitoring - Week 6

---

## Current Phase: Development (Weeks 3-5)

### Weekly Sprint Cycle

**Every Monday:**
1. Review PROGRESS.md for the week's tasks
2. Create GitHub issues for all tasks
3. Estimate time for each task (size: S/M/L/XL)
4. Prioritize tasks (P0/P1/P2)

**Daily Development:**
1. Pick next task from GitHub issues
2. Create feature branch
3. Implement with tests
4. Create PR
5. Review own PR (simulate code review)
6. Merge after CI passes
7. Close issue
8. Update PROGRESS.md

**Every Friday:**
- Sprint retrospective (what went well, what to improve)
- Demo working features
- Plan next week

---

## Professional Git Workflow

### Branch Strategy

```
main (production-ready code)
  ↓
develop (integration branch) - NOT USED YET, add in Week 6
  ↓
feature/task-name (individual features)
```

**For now (Weeks 3-5):** Use `main` + feature branches

**Week 6 onward:** Add `develop` branch for staging

### Branch Naming Convention

```
feature/week3-draft-reply-generation
bugfix/gmail-token-refresh-fails
hotfix/telegram-bot-crash
refactor/database-query-optimization
docs/update-api-documentation
```

**Pattern:** `<type>/<short-description>`

Types:
- `feature/` - New functionality
- `bugfix/` - Fix for a bug
- `hotfix/` - Urgent production fix
- `refactor/` - Code improvement (no behavior change)
- `docs/` - Documentation only
- `test/` - Test improvements

---

## GitHub Issue Workflow

### Creating Issues

**Every task from PROGRESS.md becomes a GitHub issue.**

**Use templates:**
- Features: `docs/USER_STORY_TEMPLATE.md`
- Bugs: `docs/BUG_REPORT_TEMPLATE.md`

**Labels:**
```
Type: user-story, bug, enhancement, documentation
Size: size:S, size:M, size:L, size:XL
Priority: priority:critical, priority:high, priority:medium, priority:low
Area: area:api, area:frontend, area:ai, area:database, area:telegram
Status: in-progress, blocked, ready-for-review
```

**Example Issue Creation:**
```bash
gh issue create \
  --title "Week 3 Task 1: Draft Reply Generation" \
  --label "user-story,size:M,priority:high,area:ai" \
  --body-file docs/USER_STORY_TEMPLATE.md
```

### Issue Lifecycle

```
Open → In Progress → PR Created → Review → Merged → Closed
```

**Track with labels:**
1. Create issue: No status label
2. Start work: Add `in-progress` label
3. Create PR: Add PR link in comment
4. After merge: Close issue with comment about completion

---

## Pull Request Workflow

### PR Template (Already exists: .github/PULL_REQUEST_TEMPLATE.md)

Every PR must include:
- [ ] What changed (summary)
- [ ] Why changed (context)
- [ ] How to test
- [ ] Screenshots (for UI changes)
- [ ] Test coverage (must be >80%)
- [ ] Checklist completed

### PR Process

**1. Create PR:**
```bash
git checkout -b feature/draft-reply-generation
# ... make changes ...
git add .
git commit -m "feat: implement draft reply generation

- Add 3-tone reply system
- Store drafts in database
- Add comprehensive tests

Closes #5"

git push -u origin feature/draft-reply-generation

gh pr create \
  --title "Week 3 Task 1: Draft Reply Generation" \
  --body "Closes #5

## Summary
Implements AI-powered reply drafting with 3 tone options.

## Changes
- src/ai/reply_generator.py - New reply generation module
- tests/test_reply_generator.py - Comprehensive test suite

## Test Coverage
85% (above 80% threshold)

## Testing
- [x] All tests pass locally
- [x] Linting clean
- [x] Manual testing with real emails"
```

**2. CI Runs Automatically:**
- GitHub Actions triggers
- Runs tests
- Checks linting
- Checks coverage
- Shows ✅ or ❌ on PR

**3. Self Code Review:**
- Review your own PR on GitHub
- Check for:
  - Code quality
  - Test coverage
  - Documentation
  - No debug code left
  - No secrets committed

**4. Address CI Failures:**
If CI fails:
```bash
# Fix the issue locally
git add .
git commit -m "fix: address CI lint failures"
git push
# CI re-runs automatically
```

**5. Merge:**
```bash
gh pr merge --squash --delete-branch
```

**6. Post-Merge:**
```bash
# Link PR to issue
gh issue comment 5 --body "✅ Merged in PR #12"

# Close issue
gh issue close 5 --reason completed

# Update PROGRESS.md
git checkout main
git pull
# Edit PROGRESS.md to mark task complete
git add docs/PROGRESS.md
git commit -m "docs: mark Week 3 Task 1 complete"
git push
```

---

## Continuous Integration (CI)

### Current CI Checks (.github/workflows/)

**tests.yml** - Runs on every PR:
```yaml
- Install dependencies
- Run pytest with coverage
- Fail if coverage <80%
- Upload coverage report
```

**lint.yml** - Runs on every PR:
```yaml
- Check code formatting (black)
- Check linting (flake8)
- Check import sorting (isort)
- Check type hints (mypy)
```

### Quality Gates

**No PR can be merged unless:**
- ✅ All tests pass
- ✅ Coverage ≥80%
- ✅ Linting passes (0 errors)
- ✅ Type hints present
- ✅ PR template completed

This simulates **merge blockers** at big companies.

---

## Code Quality Standards

### Required for Every Feature

**1. Type Hints:**
```python
# ✅ Good
def generate_reply(email: dict, tone: str) -> str:
    pass

# ❌ Bad
def generate_reply(email, tone):
    pass
```

**2. Docstrings:**
```python
# ✅ Good
def generate_reply(email: dict, tone: str) -> str:
    """Generate email reply with specified tone.
    
    Args:
        email: Email data dictionary with 'subject' and 'body'
        tone: Reply tone ('professional', 'friendly', 'brief')
    
    Returns:
        Generated reply text
    
    Raises:
        ValueError: If tone is invalid
    """
    pass
```

**3. Tests:**
```python
# Every function needs:
# - Unit test (mocked dependencies)
# - Integration test (real APIs, if applicable)
# - Edge case tests
# - Error handling tests
```

**4. Code Style:**
```bash
# Format with black
black src/ tests/

# Lint with flake8
flake8 src/ tests/ --max-line-length=100

# Sort imports
isort src/ tests/
```

---

## Testing Strategy (Professional Standard)

### Test Pyramid

```
       /\
      /E2E\      ← Few (1-2 per major feature)
     /------\
    /Integration\  ← Some (5-10 per feature)
   /------------\
  /  Unit Tests  \  ← Many (20-50 per feature)
 /________________\
```

### Test Organization

```
tests/
├── unit/                    # Fast, isolated tests
│   ├── test_gmail_auth.py
│   ├── test_analyzer.py
│   └── test_reply_generator.py
├── integration/             # Tests with real APIs
│   ├── test_gmail_integration.py
│   ├── test_claude_integration.py
│   └── test_database_integration.py
├── e2e/                     # End-to-end workflows
│   └── test_full_workflow.py
└── fixtures/                # Test data
    └── sample_emails.json
```

### Running Tests

```bash
# All tests
pytest tests/ -v

# Only fast tests (unit)
pytest tests/unit/ -v

# With coverage
pytest tests/ -v --cov=src --cov-report=html

# Specific test
pytest tests/unit/test_reply_generator.py::test_professional_tone -v
```

---

## Documentation Standards

### Required Documentation

**1. README.md** (project overview)
- What the project does
- How to set up
- How to run
- How to test
- How to deploy (Week 6+)

**2. CLAUDE.md** (for AI development)
- Project context
- Development workflow
- Testing requirements
- Common commands

**3. PROGRESS.md** (task tracking)
- Weekly breakdown
- Task status
- Completion dates

**4. API Documentation** (if applicable)
- Endpoint descriptions
- Request/response examples
- Error codes

**5. Deployment Runbook** (Week 6)
- How to deploy
- Environment variables
- Rollback procedure

---

## Metrics & Reporting

### Track These Metrics

**Development Velocity:**
- Tasks completed per week
- Average time per task
- PR merge time (creation → merge)

**Code Quality:**
- Test coverage %
- Lint errors (should be 0)
- PR size (lines changed)

**CI/CD Performance:**
- CI run time
- CI success rate
- Deployment frequency (Week 6+)

### Weekly Report Template

```markdown
## Week N Sprint Report

**Dates:** [start] - [end]

**Planned vs Actual:**
- Planned: 5 tasks
- Completed: 4 tasks
- Carried over: 1 task

**Metrics:**
- PRs merged: 4
- Test coverage: 87% (↑3% from last week)
- CI success rate: 95%
- Average PR size: 120 lines

**What went well:**
- Completed draft reply feature ahead of schedule
- Improved test coverage significantly
- No CI failures this week

**Challenges:**
- Thread context management took longer than estimated
- Claude API rate limits hit during testing

**Next week focus:**
- Complete Week 3 remaining tasks
- Improve integration test coverage
- Start Week 4 planning
```

---

## Week 6: Adding Continuous Deployment (CD)

### Deployment Strategy (Big Company Approach)

**Environments:**

1. **Development** (local)
   - Run on your laptop
   - For active development

2. **Staging** (AWS EC2 #1)
   - Auto-deploys from `main` branch
   - For testing before production
   - Uses test Gmail/Telegram accounts

3. **Production** (AWS EC2 #2)
   - Manual deployment (after approval)
   - Real users
   - Requires approval from "tech lead" (you)

**Deployment Pipeline:**

```
Push to main → CI passes → Auto-deploy to Staging
                              ↓
                         Test on staging
                              ↓
                    Manual approval needed
                              ↓
                    Deploy to Production
                              ↓
                    Monitor for 24 hours
```

### Deployment Workflow (.github/workflows/deploy.yml)

```yaml
name: Deploy

on:
  push:
    branches: [main]
  workflow_dispatch:  # Manual trigger

jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    steps:
      - Run tests
      - Deploy to AWS Staging
      - Post deployment notification
  
  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment:
      name: production
      # Requires manual approval
    steps:
      - Deploy to AWS Production
      - Run smoke tests
      - Post deployment notification
```

### Infrastructure as Code

**AWS Resources (Week 6):**
```
- 2 EC2 instances (staging + production)
- 1 RDS database (optional, or use SQLite)
- Security groups
- SSH keys
- Monitoring/CloudWatch
```

**Document everything in:**
- `docs/DEPLOYMENT.md`
- `docs/AWS_SETUP.md`
- `docs/RUNBOOK.md`

---

## Professional Practices Checklist

### Every Feature Must Have:

- [ ] GitHub issue created (from PROGRESS.md)
- [ ] Feature branch created
- [ ] Code implemented with type hints
- [ ] Docstrings for all public functions
- [ ] Unit tests written (>80% coverage)
- [ ] Integration tests written (where applicable)
- [ ] Linting passes (black, flake8)
- [ ] PR created with template completed
- [ ] CI passes (tests + lint)
- [ ] Self code review performed
- [ ] PR merged to main
- [ ] Issue closed
- [ ] PROGRESS.md updated
- [ ] README updated (if needed)

### Every Week Must Have:

- [ ] Sprint planning (Monday)
- [ ] Issues created for all tasks
- [ ] Daily progress on tasks
- [ ] Sprint report (Friday)
- [ ] Demo of completed features
- [ ] Retrospective notes

---

## Tools & Commands Reference

### GitHub CLI Commands

```bash
# Issues
gh issue list
gh issue create --title "..." --body-file template.md
gh issue view <number>
gh issue close <number>

# PRs
gh pr create --title "..." --body "..."
gh pr list
gh pr view <number>
gh pr checks <number>
gh pr merge <number> --squash

# Workflow
gh workflow list
gh workflow run deploy.yml
gh run list
```

### Git Commands

```bash
# Feature workflow
git checkout -b feature/task-name
git add .
git commit -m "feat: description"
git push -u origin feature/task-name

# Update from main
git checkout main
git pull
git checkout feature/task-name
git merge main

# Clean up after merge
git branch -d feature/task-name
git remote prune origin
```

### Testing Commands

```bash
# Run tests
pytest tests/ -v
pytest tests/ -v --cov=src --cov-report=term
pytest tests/unit/ -v  # Only unit tests

# Coverage report
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html

# Specific test
pytest tests/unit/test_file.py::test_function -v
```

### Code Quality Commands

```bash
# Format
black src/ tests/
isort src/ tests/

# Lint
flake8 src/ tests/ --max-line-length=100

# Type check
mypy src/ --ignore-missing-imports
```

---

## Example: Complete Feature Development Flow

### Task: Implement Draft Reply Generation (Week 3 Task 1)

**Step 1: Create Issue**
```bash
gh issue create \
  --title "Week 3 Task 1: Draft Reply Generation" \
  --label "user-story,size:M,priority:high,area:ai" \
  --body "$(cat docs/USER_STORY_TEMPLATE.md)"
# Returns: Created issue #5
```

**Step 2: Start Work**
```bash
git checkout main
git pull
git checkout -b feature/draft-reply-generation

gh issue edit 5 --add-label "in-progress"
```

**Step 3: Implement**
```bash
# Create src/ai/reply_generator.py
# Create tests/unit/test_reply_generator.py
# Create tests/integration/test_reply_integration.py

# Run tests locally
pytest tests/ -v --cov=src

# Format code
black src/ tests/
flake8 src/ tests/
```

**Step 4: Commit & Push**
```bash
git add .
git commit -m "feat: implement draft reply generation

- Add reply_generator.py with 3-tone system
- Add comprehensive test suite (87% coverage)
- Update database schema for drafts

Closes #5"

git push -u origin feature/draft-reply-generation
```

**Step 5: Create PR**
```bash
gh pr create \
  --title "Week 3 Task 1: Draft Reply Generation" \
  --body "Closes #5

## Summary
Implements AI-powered reply drafting with professional, friendly, and brief tones.

## Changes
- src/ai/reply_generator.py - Main implementation
- src/ai/prompt_templates.py - Tone-specific prompts
- src/database/db.py - Draft storage methods
- tests/unit/test_reply_generator.py - Unit tests
- tests/integration/test_reply_integration.py - Integration tests

## Testing
- [x] All tests pass (25 tests)
- [x] Coverage 87% (above 80%)
- [x] Linting clean
- [x] Manual testing with real emails

## Screenshots
[If UI changes]"

# Returns: Created PR #12
```

**Step 6: Monitor CI**
```bash
gh pr checks 12 --watch
# CI runs: tests.yml, lint.yml
# Wait for ✅
```

**Step 7: Self Review**
- Open PR on GitHub
- Review code changes
- Check for mistakes
- Verify tests cover edge cases

**Step 8: Merge**
```bash
gh pr merge 12 --squash --delete-branch
```

**Step 9: Post-Merge**
```bash
# Link PR to issue
gh issue comment 5 --body "✅ Completed in PR #12

Test coverage: 87%
Duration: 4 hours"

# Close issue
gh issue close 5 --reason completed

# Update docs
git checkout main
git pull
# Edit docs/PROGRESS.md: Task 1 ✅
git add docs/PROGRESS.md
git commit -m "docs: mark Week 3 Task 1 complete"
git push
```

**Step 10: Sprint Report**
Update weekly metrics in docs/SPRINT_REPORTS.md

---

## Portfolio Value

This workflow demonstrates to employers:

✅ **Professional Git workflow** (branching, PRs, reviews)
✅ **CI/CD experience** (automated testing, deployment)
✅ **Quality standards** (testing, linting, coverage)
✅ **Documentation skills** (README, runbooks, ADRs)
✅ **Project management** (issues, sprint planning)
✅ **Self-direction** (can work independently)
✅ **Production experience** (AWS deployment, monitoring)

**Resume bullet points:**
- "Implemented CI/CD pipeline with GitHub Actions, achieving 95% test coverage and 100% automated deployment success rate"
- "Followed professional Git workflow with feature branches, pull requests, and automated quality gates"
- "Deployed production application to AWS EC2 with staging/production environments and zero-downtime deployments"

---

## Next Steps

**Week 3-5:**
- Follow this workflow for every task
- Build muscle memory for professional practices
- Accumulate portfolio of well-documented PRs

**Week 6:**
- Add deployment pipeline
- Set up AWS staging + production
- Add monitoring and alerts

**Week 7:**
- Polish documentation
- Create deployment demo video
- Write case study about your workflow

---

**Last Updated:** Week 3
**Status:** Active Development Phase
