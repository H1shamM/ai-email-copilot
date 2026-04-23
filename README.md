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
- `GET  /` — health check
- `GET  /emails` — fetch live from Gmail (no DB write)
- `POST /emails/fetch` — fetch and store in SQLite
- `POST /emails/analyze` — run Claude analysis on unprocessed emails
- `GET  /emails/analyzed` — list emails with stored analysis

## Development

```bash
pytest tests/ --cov=app
black app/ tests/
flake8 app/ tests/
```

See [`docs/GITHUB_WORKFLOW.md`](docs/GITHUB_WORKFLOW.md) for the branch/PR/CI process.

## Project Structure

```
app/
├── main.py            FastAPI app + endpoints
├── gmail/             OAuth + Gmail API client
├── ai/                Claude API integration
├── database/          SQLite layer
└── models/            Pydantic schemas
tests/
├── unit/
└── integration/
```