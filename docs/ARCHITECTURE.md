# Architecture

AI Email Copilot is a personal Gmail assistant driven entirely from Telegram. A single
FastAPI process receives Telegram updates over a webhook, routes them through the bot's
command handlers, and composes four layers — **LLM (Claude)**, **SQLite**, and the two
**external integrations (Gmail + Google Calendar)** — to read, analyze, and act on email.
The Week 5 `/agent` command ties them together: Claude plans with native tool-use, runs
read-only tools itself, and proposes mutating actions for the user to approve.

## System flowchart

```mermaid
flowchart TB
    User([User in Telegram])

    subgraph EXT["External services"]
        TG["Telegram Bot API"]
        ANT["Anthropic API<br/>Claude Sonnet 4"]
        GM["Gmail API"]
        GC["Google Calendar API"]
    end

    subgraph EC2["AWS EC2 · systemd · Caddy (TLS 443)"]
        Caddy["Caddy reverse proxy"]
        subgraph APP["FastAPI · uvicorn :8000"]
            WH["POST /telegram/webhook<br/>(secret-token check)"]
            REST["REST: /emails · /health"]
            BOT["python-telegram-bot<br/>handlers + @authorized_only"]
            PUSH["Push scheduler<br/>(apscheduler)"]

            subgraph AI["AI layer · app/ai"]
                AGENT[["agent.py<br/>tool-use loop"]]
                ANALYZE["analyzer"]
                REPLY["reply_generator"]
                MEET["meeting_detector"]
            end

            GSVC["gmail/service<br/>OAuth token.pickle"]
            CSVC["calendar/service<br/>+ scheduler"]
            DB[("SQLite<br/>emails · draft_replies · calendar_events<br/>followups · telegram_users · prefs")]
        end
    end

    User <-->|commands / replies| TG
    TG -->|update + secret token| Caddy
    Caddy --> WH --> BOT
    REST -. backend/testing .-> GSVC
    PUSH -->|every N min: fetch → analyze → notify| BOT

    BOT --> AGENT
    BOT --> ANALYZE
    BOT --> REPLY
    BOT --> MEET
    BOT --> GSVC
    BOT --> CSVC
    BOT --> DB

    AGENT -. read-only tools .-> ANALYZE
    AGENT -. read-only tools .-> REPLY
    AGENT -. read-only tools .-> GSVC
    AGENT -. read-only tools .-> CSVC
    AGENT -. read-only tools .-> DB

    ANALYZE -->|messages.create| ANT
    REPLY -->|messages.create| ANT
    MEET -->|messages.create| ANT
    AGENT -->|messages.create · tools=…| ANT

    GSVC -->|read + send| GM
    CSVC -->|events.insert · freebusy| GC
    BOT -->|notifications| TG

    classDef ext fill:#fde7c7,stroke:#c77f1a,color:#000;
    classDef agent fill:#cfe8ff,stroke:#1a6fc7,color:#000,font-weight:bold;
    classDef store fill:#e7f7e0,stroke:#3a9a3a,color:#000;
    class TG,ANT,GM,GC ext;
    class AGENT agent;
    class DB store;
```

## `/agent` request flow (the agentic centerpiece)

The agent satisfies the program's *advanced LLM* requirement with **both** Function Calling
and Agentic Flow. Read-only tools execute live so Claude reasons over real inbox/calendar
data; mutating tools are never run inside the loop — they are queued and gated behind
explicit user approval (the same approve-before-act model as `/reply` and `/schedule`).

```mermaid
sequenceDiagram
    actor U as User (Telegram)
    participant B as Bot handler<br/>(/agent)
    participant A as agent.py loop
    participant C as Claude (tools)
    participant T as Tools<br/>(Gmail · Calendar · DB)

    U->>B: /agent "reply to Alice and schedule it"
    B->>A: run_agent(instruction)
    loop until end_turn (max 8 rounds)
        A->>C: messages.create(tools=…)
        alt read-only tool_use
            C-->>A: list / get / analyze / draft_reply
            A->>T: execute tool
            T-->>A: result
            A->>C: tool_result
        else mutating tool_use
            C-->>A: send_reply / create_calendar_event
            A->>A: queue + reply PENDING_APPROVAL
        end
    end
    A-->>B: (final_text, pending_actions)
    B-->>U: proposed actions + ✅ Approve / ✖ Cancel
    U->>B: tap Approve
    B->>A: execute_action(...) per queued action
    A->>T: send_reply / create_event (now for real)
    T-->>B: result
    B-->>U: ✅ per-action results
```

## Components

| Layer | Module(s) | Responsibility |
|---|---|---|
| Entry / API | `app/main.py` | FastAPI app: `/telegram/webhook` (production traffic), `/health`, REST `/emails*` (backend/testing) |
| Bot | `app/telegram/{bot,handlers,formatting,conversations}.py` | Command routing, single-user auth (`@authorized_only`), inline-keyboard approve-before-act, MarkdownV2 formatting |
| Scheduler | `app/telegram/push.py` | Periodic unread → analyze → notify on high-urgency mail (apscheduler) |
| LLM | `app/ai/{agent,analyzer,reply_generator,meeting_detector,prompts}.py` | Claude Sonnet 4: analysis, 3-tone replies, meeting extraction, and the tool-use agent |
| Gmail | `app/gmail/{auth,service}.py` | OAuth (`token.pickle`), fetch + threaded send |
| Calendar | `app/calendar/{service,scheduler}.py` | `events.insert`, freebusy conflict check, event-body building |
| Storage | `app/database/db.py` | SQLite schema + helpers (`emails`, `draft_replies`, `calendar_events`, `followups`, `telegram_users`, `user_preferences`) |
| Deployment | `infra/`, `.github/workflows/deploy.yml` | EC2 + Caddy (auto-TLS) + systemd; GitHub Actions OIDC → SSM auto-deploy on push to `main` |

## Key flows

- **Pull command** (`/unread`, `/inbox`): Telegram → webhook → handler → Gmail/DB → formatted reply.
- **Analyze**: handler → `analyzer` → Claude → DB; if `action_required == "Schedule"`, `meeting_detector` persists a `calendar_events` row.
- **Reply / Schedule**: generate or detect → present with inline buttons → on approval, `gmail.send_reply` / `calendar.scheduler.create_event`.
- **Agent** (`/agent`): one natural-language instruction → tool-use loop (read-only live, mutating queued) → approve → execute. See the sequence diagram above.
- **Push**: scheduler tick → fetch unread → analyze → notify when `urgency_score ≥ threshold`.

> Diagrams are [Mermaid](https://mermaid.js.org/) — they render on GitHub and can be exported to PNG/SVG for the demo video via the [Mermaid Live Editor](https://mermaid.live).