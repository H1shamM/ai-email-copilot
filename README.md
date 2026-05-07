# AI Email Copilot

AI-powered Gmail assistant that fetches emails, analyzes them with Claude, generates draft replies, and helps automate inbox management.

See [`docs/PRD.md`](docs/PRD.md) for the full product spec and [`docs/PROGRESS.md`](docs/PROGRESS.md) for weekly status.

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env  # then fill in ANTHROPIC_API_KEY
```

You also need a Google Cloud OAuth credentials file at `credentials.json` (see [Gmail API quickstart](https://developers.google.com/gmail/api/quickstart/python)).

## Run

```bash
uvicorn app.main:app --reload
```

Endpoints:
- `GET  /` — root banner
- `GET  /health` — liveness probe (used by Caddy + monitoring)
- `GET  /emails` — fetch live from Gmail (no DB write)
- `POST /emails/fetch` — fetch and store in SQLite
- `POST /emails/analyze` — run Claude analysis on unprocessed emails
- `GET  /emails/analyzed` — list emails with stored analysis
- `POST /telegram/webhook` — Telegram update handler (production traffic enters here)

## Development

```bash
pytest tests/ --cov=app
black app/ tests/
flake8 app/ tests/
```

See [`docs/GITHUB_WORKFLOW.md`](docs/GITHUB_WORKFLOW.md) for the branch/PR/CI process.

## Deployment

For production, the bot runs on a single AWS EC2 instance behind Caddy/HTTPS at a stable `<eip>.nip.io` hostname (no domain required).

Step-by-step CLI runbook: [`docs/AWS_DEPLOY.md`](docs/AWS_DEPLOY.md). Steady-state cost ~$5/month plus Anthropic API charges. Templates for Caddy + systemd live in [`infra/`](infra/).

**CI/CD**: every push to `main` auto-deploys via [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) — GitHub OIDC → AWS STS → SSM `send-command` runs `git checkout <sha> && pip install && systemctl restart copilot`, then smoke-checks `/health`. No long-lived AWS keys, no SSH. Rollback is "Re-run all jobs" on a previous successful run. Setup steps in [`docs/AWS_DEPLOY.md`](docs/AWS_DEPLOY.md) under *CI/CD*.

## Project Structure

```
app/
├── main.py            FastAPI app + endpoints
├── gmail/             OAuth + Gmail API client
├── ai/                Claude API integration
├── database/          SQLite layer
├── telegram/          bot, handlers, formatting, push scheduler
└── models/            Pydantic schemas
tests/
├── unit/
└── integration/
infra/
├── Caddyfile.template
└── copilot.service
docs/
├── PRD.md, PROGRESS.md
├── PROFESSIONAL_WORKFLOW.md
└── AWS_DEPLOY.md
```