# Smart Email Assistant - Product Requirements Document

**Project Timeline:** 7 weeks (March 15 - May 9, 2026)  
**Current Status:** Week 1 - Setup & Ideation  
**Primary Goal:** Build a functional AI-powered Gmail assistant while learning LLM integration, agentic workflows, and API development

---

## Executive Summary

An AI-powered email assistant that connects to Gmail, analyzes emails using Claude API, generates contextual reply suggestions, extracts calendar events, and helps users manage their inbox efficiently. This project focuses on practical skill development in API integration, prompt engineering, and building useful AI applications.

**Core Value:** Reduce email processing time by 50%+ through intelligent automation and AI-assisted responses.

---

## Product Goals

### Learning Objectives
1. **API Integration**: Master Gmail API and Google Calendar API
2. **LLM Development**: Learn prompt engineering, function calling, and agentic workflows
3. **Full-Stack Development**: Build end-to-end application (backend + frontend + database)
4. **Portfolio Quality**: Create a demonstrable, real-world AI application

### Success Criteria
- Successfully authenticate and read Gmail messages
- Generate useful draft replies with 70%+ acceptance rate
- Correctly identify action items and calendar events
- Complete working demo by Week 6
- Deploy publicly accessible version (optional)

---

## Technical Stack

### Backend
```
- Python 3.10+
- Flask or FastAPI (web framework)
- gmail-api-python-client (Gmail integration)
- google-auth-oauthlib (authentication)
- anthropic (Claude API)
- SQLite (database)
```

### Frontend
```
- HTML/CSS/JavaScript (Week 1-3: simple)
- React + Tailwind CSS (Week 4+: optional upgrade)
- Fetch API for backend communication
```

### Infrastructure
```
- Local development (Week 1-5)
- Git/GitHub for version control
- Optional: Render/Railway deployment (Week 6)
```

---

## Feature Specification

## MUST HAVE Features (MVP)

### Feature 1: Gmail Authentication & Email Fetching
**Priority:** P0 (Critical)  
**Timeline:** Week 1-2

**Requirements:**
- Implement OAuth 2.0 flow for Gmail API
- Store credentials securely (credentials.json, token.json)
- Fetch last 50 unread emails
- Handle pagination for large inboxes
- Display: sender, subject, snippet, date, thread ID

**Technical Details:**
```python
# Required scopes:
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send'
]

# API endpoints to use:
- users.messages.list()
- users.messages.get()
- users.messages.modify()
- users.messages.send()
```

**Success Metrics:**
- Can authenticate with Gmail
- Fetch and display 50 emails in <3 seconds
- Handle rate limiting gracefully

---

### Feature 2: AI Email Analysis
**Priority:** P0 (Critical)  
**Timeline:** Week 2-3

**Requirements:**
- Send email content to Claude API
- Extract structured insights:
  - Summary (2-3 sentences)
  - Category (Work, Personal, Newsletter, Finance, etc.)
  - Sentiment (Urgent, Casual, Formal)
  - Action required (Reply, Schedule, Read, Archive)
  - Key entities (people, dates, locations)

**Prompt Template:**
```
Analyze this email and provide structured output:

EMAIL:
From: {sender}
Subject: {subject}
Body: {body}

Respond in JSON format:
{
  "summary": "2-3 sentence summary",
  "category": "Work|Personal|Newsletter|Finance|Travel|Shopping|Other",
  "sentiment": "Urgent|Casual|Formal",
  "action_required": "Reply|Schedule|Read|Archive|Flag",
  "key_dates": ["2024-03-20"],
  "key_people": ["John Smith"],
  "urgency_score": 1-10
}
```

**Technical Implementation:**
- Use Claude Sonnet 4 (fast, cost-effective)
- Implement caching for similar emails
- Handle API errors and retries
- Store analysis results in database

---

### Feature 3: Smart Reply Generation
**Priority:** P0 (Critical)  
**Timeline:** Week 3-4

**Requirements:**
- Generate 3 draft replies with different tones:
  1. **Professional**: Formal, detailed, polite
  2. **Friendly**: Casual, warm, conversational
  3. **Brief**: Short, to-the-point, efficient
- Consider email thread context
- Preserve user's writing style (learn from sent emails)
- Allow editing before sending

**Prompt Template:**
```
Generate a reply to this email thread.

CONTEXT:
Original Email: {original_email}
Thread History: {thread_context}

USER PREFERENCES:
- Tone: {tone}
- Length: {length}
- Include: {include_elements}

Generate a reply that:
1. Addresses all questions/requests
2. Maintains appropriate tone
3. Is {length} in length
4. Sounds natural and human

REPLY:
```

**Technical Details:**
- Store thread context (last 5 messages)
- Implement tone controls (slider or dropdown)
- Add "regenerate" option for unsatisfied drafts
- Track sent replies to learn user preferences

---

### Feature 4: Action Detection & Recommendations
**Priority:** P0 (Critical)  
**Timeline:** Week 3

**Requirements:**
- Detect actionable items in emails:
  - Meeting requests → Extract date/time/participants
  - Tasks/deadlines → Create reminder
  - Questions → Suggest reply
  - Information → Archive with category
- Display recommended action prominently
- One-click action execution

**Detection Logic:**
```python
# Meeting indicators:
keywords = ["meet", "meeting", "call", "zoom", "schedule", "available"]
date_patterns = ["tomorrow", "next week", "monday", "3pm"]

# Task indicators:
keywords = ["deadline", "by EOD", "ASAP", "urgent", "complete"]

# Question indicators:
contains = ["?", "can you", "could you", "would you", "please"]
```

---

## SHOULD HAVE Features (Enhanced)

### Feature 5: Google Calendar Integration
**Priority:** P1  
**Timeline:** Week 4

**Requirements:**
- Detect meeting requests in email body
- Extract: title, date, time, duration, participants, location
- Parse natural language dates ("next Tuesday at 3pm")
- Create calendar event with one click
- Handle timezone conversions
- Suggest available time slots for ambiguous requests

**Technical Details:**
```python
# Required scopes:
SCOPES.append('https://www.googleapis.com/auth/calendar')

# Calendar API endpoints:
- events.insert()
- events.list() # check availability
- freebusy.query() # find free slots
```

**Natural Language Date Parsing:**
```python
# Use dateutil.parser or custom regex
from dateutil import parser

examples = [
    "next Tuesday at 3pm",
    "tomorrow morning",
    "March 20th at 2:30pm",
    "in 2 hours"
]
```

---

### Feature 6: Smart Categorization
**Priority:** P1  
**Timeline:** Week 5

**Requirements:**
- Auto-categorize emails using AI
- Learn from user corrections
- Bulk actions by category (archive all newsletters)
- Custom category creation
- Category-based filtering

**Categories:**
```
- Work
- Personal
- Finance (invoices, receipts, statements)
- Travel (bookings, confirmations)
- Shopping (orders, shipping)
- Newsletters
- Social (social media notifications)
- Promotions
- Other
```

**ML Approach:**
- Use Claude for initial categorization
- Store user corrections in database
- Build pattern matching from corrections
- Combine AI + rules for accuracy

---

### Feature 7: Follow-up Tracking
**Priority:** P1  
**Timeline:** Week 5

**Requirements:**
- Detect emails that need follow-up
- Set automatic reminders (3 days, 1 week)
- Track if reply was sent
- Nudge user for pending follow-ups
- "Snooze" feature to defer emails

**Implementation:**
```python
# Database schema:
followups:
  - email_id
  - remind_at (datetime)
  - reason (waiting_for_reply, task_deadline, etc.)
  - status (pending, completed, snoozed)
  - snoozed_until (datetime, nullable)
```

---

## COULD HAVE Features (Polish)

### Feature 8: Email Thread Analysis
**Priority:** P2  
**Timeline:** Week 6

- Analyze full conversation threads
- Summarize multi-email threads (not just latest)
- Detect conversation conclusion (no reply needed)
- Show conversation sentiment over time

### Feature 9: Attachment Intelligence
**Priority:** P2  
**Timeline:** Week 6

- Detect attachment types (PDF, image, spreadsheet)
- Extract text from PDFs
- Summarize document content
- Suggest actions (save to folder, forward)

### Feature 10: Natural Language Search
**Priority:** P2  
**Timeline:** Week 6

- Search emails using natural language
- "Find the email about the project deadline from last week"
- Semantic search (not just keyword matching)
- Search across body, subject, attachments

---

## WON'T HAVE (Out of Scope)

These features are explicitly excluded to maintain focus:

- ❌ Autonomous email sending (no sending without user approval)
- ❌ Multi-account support (only primary Gmail)
- ❌ Mobile app (web interface only)
- ❌ Outlook/Yahoo integration (Gmail only)
- ❌ Spam/scam detection (Gmail handles this)
- ❌ Email templates or canned responses
- ❌ Email scheduling or delayed sending
- ❌ CRM integration
- ❌ Team/shared inbox support

---

## Database Schema

### emails
```sql
CREATE TABLE emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_message_id TEXT UNIQUE NOT NULL,
    thread_id TEXT,
    sender TEXT NOT NULL,
    subject TEXT,
    body TEXT,
    snippet TEXT,
    received_date DATETIME,
    
    -- AI Analysis
    ai_summary TEXT,
    category TEXT,
    sentiment TEXT,
    action_required TEXT,
    urgency_score INTEGER,
    
    -- Status
    is_read BOOLEAN DEFAULT FALSE,
    is_archived BOOLEAN DEFAULT FALSE,
    is_starred BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    processed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_gmail_id ON emails(gmail_message_id);
CREATE INDEX idx_category ON emails(category);
CREATE INDEX idx_received_date ON emails(received_date);
```

### draft_replies
```sql
CREATE TABLE draft_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER NOT NULL,
    tone TEXT NOT NULL, -- professional, friendly, brief
    draft_text TEXT NOT NULL,
    was_sent BOOLEAN DEFAULT FALSE,
    sent_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email_id) REFERENCES emails(id)
);
```

### calendar_events
```sql
CREATE TABLE calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER NOT NULL,
    google_event_id TEXT,
    title TEXT NOT NULL,
    event_date DATE,
    event_time TIME,
    duration_minutes INTEGER,
    participants TEXT, -- JSON array
    location TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email_id) REFERENCES emails(id)
);
```

### followups
```sql
CREATE TABLE followups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER NOT NULL,
    remind_at DATETIME NOT NULL,
    reason TEXT,
    status TEXT DEFAULT 'pending', -- pending, completed, snoozed
    snoozed_until DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email_id) REFERENCES emails(id)
);
```

### user_preferences
```sql
CREATE TABLE user_preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## API Integration Details

### Gmail API

**Authentication Flow:**
1. User visits `/auth` endpoint
2. Redirect to Google OAuth consent screen
3. User grants permissions
4. Exchange authorization code for tokens
5. Store tokens securely (token.json)
6. Refresh tokens automatically when expired

**Rate Limits:**
- 250 quota units per user per second
- 1 billion quota units per day
- messages.list = 5 units
- messages.get = 5 units
- messages.send = 100 units

**Error Handling:**
```python
from googleapiclient.errors import HttpError

try:
    results = service.users().messages().list(userId='me').execute()
except HttpError as error:
    if error.resp.status == 429:
        # Rate limit hit - implement exponential backoff
        time.sleep(2 ** retry_count)
    elif error.resp.status == 401:
        # Token expired - refresh
        refresh_token()
```

### Claude API

**Model Selection:**
- Use `claude-sonnet-4-20250514` (best cost/performance)
- Fallback to `claude-haiku-4` if budget constrained

**Cost Optimization:**
```python
# Prompt caching for repeated content
# Cache email analysis prompt template
# Batch similar emails together
# Use shorter prompts for simple tasks

# Example costs (approximate):
# Sonnet 4: $3 per million input tokens, $15 per million output
# Average email analysis: ~500 tokens in, ~200 tokens out
# Cost per email: ~$0.004
```

**Best Practices:**
- Use system prompts for consistent behavior
- Implement streaming for better UX
- Add retry logic with exponential backoff
- Cache common prompts (save 90% on repeated content)

---

## Week-by-Week Implementation Plan

## Week 1: Setup & Project Definition (Mar 15-21)

### Goals
- ✅ Development environment ready
- ✅ Gmail API connection working
- ✅ Can fetch and display 1 email

### Tasks

**Day 1-2: Environment Setup**
```bash
# Create project structure
mkdir email-assistant
cd email-assistant
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib anthropic flask python-dotenv

# Create project structure
mkdir -p src/{auth,email,ai,database,ui}
touch src/__init__.py
touch src/auth/__init__.py src/email/__init__.py src/ai/__init__.py
```

**Day 3-4: Gmail API Setup**
1. Go to https://console.cloud.google.com/
2. Create new project "Email Assistant"
3. Enable Gmail API
4. Create OAuth 2.0 credentials
5. Download credentials.json
6. Create `src/auth/gmail_auth.py`:

```python
import os.path
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('gmail', 'v1', credentials=creds)
```

**Day 5-6: First Email Fetch**
Create `src/email/fetcher.py`:
```python
def fetch_recent_emails(service, max_results=10):
    results = service.users().messages().list(
        userId='me',
        maxResults=max_results,
        q='is:unread'
    ).execute()
    
    messages = results.get('messages', [])
    emails = []
    
    for msg in messages:
        email_data = service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='full'
        ).execute()
        
        emails.append(parse_email(email_data))
    
    return emails

def parse_email(email_data):
    headers = email_data['payload']['headers']
    
    return {
        'id': email_data['id'],
        'thread_id': email_data['threadId'],
        'sender': get_header(headers, 'From'),
        'subject': get_header(headers, 'Subject'),
        'date': get_header(headers, 'Date'),
        'snippet': email_data['snippet']
    }
```

**Day 7: Test & Document**
- Fetch 10 emails successfully
- Print to console
- Document setup process in README.md
- Commit to Git

### Deliverable
- Working authentication
- Can fetch 10 emails
- Code committed to GitHub

---

## Week 2: Integration POC + System Design (Mar 22-28)

### Goals
- ✅ Database setup complete
- ✅ Claude API integrated
- ✅ Can analyze 10 emails and store results

### Tasks

**Day 1-2: Database Setup**
Create `src/database/schema.sql` and `src/database/db.py`:
```python
import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_path='email_assistant.db'):
        self.conn = sqlite3.connect(db_path)
        self.init_schema()
    
    def init_schema(self):
        with open('src/database/schema.sql', 'r') as f:
            self.conn.executescript(f.read())
    
    def insert_email(self, email_data):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO emails (gmail_message_id, thread_id, sender, subject, body, snippet, received_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            email_data['id'],
            email_data['thread_id'],
            email_data['sender'],
            email_data['subject'],
            email_data.get('body', ''),
            email_data['snippet'],
            email_data['date']
        ))
        self.conn.commit()
        return cursor.lastrowid
```

**Day 3-4: Claude API Integration**
Create `src/ai/analyzer.py`:
```python
from anthropic import Anthropic
import json
import os

client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

def analyze_email(email_data):
    prompt = f"""Analyze this email and provide structured output in JSON format.

EMAIL:
From: {email_data['sender']}
Subject: {email_data['subject']}
Body: {email_data.get('body', email_data['snippet'])}

Provide this JSON structure:
{{
  "summary": "2-3 sentence summary",
  "category": "Work|Personal|Newsletter|Finance|Travel|Shopping|Other",
  "sentiment": "Urgent|Casual|Formal",
  "action_required": "Reply|Schedule|Read|Archive|Flag",
  "urgency_score": 1-10,
  "key_dates": [],
  "key_people": []
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    response_text = message.content[0].text
    
    # Parse JSON from response
    try:
        # Remove markdown code fences if present
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
        
        analysis = json.loads(response_text.strip())
        return analysis
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}")
        return None
```

**Day 5-6: Connect Pipeline**
Create `src/main.py`:
```python
from auth.gmail_auth import get_gmail_service
from email.fetcher import fetch_recent_emails
from ai.analyzer import analyze_email
from database.db import Database

def main():
    # Initialize
    gmail = get_gmail_service()
    db = Database()
    
    # Fetch emails
    print("Fetching emails...")
    emails = fetch_recent_emails(gmail, max_results=10)
    print(f"Found {len(emails)} emails")
    
    # Analyze each email
    for email in emails:
        print(f"\nAnalyzing: {email['subject']}")
        
        # Get AI analysis
        analysis = analyze_email(email)
        
        if analysis:
            # Store in database
            email_id = db.insert_email(email)
            db.update_analysis(email_id, analysis)
            
            print(f"  Category: {analysis['category']}")
            print(f"  Summary: {analysis['summary']}")
            print(f"  Action: {analysis['action_required']}")
    
    print("\nProcessing complete!")

if __name__ == '__main__':
    main()
```

**Day 7: System Design**
- Create architecture diagram
- Document data flow
- Write API design doc
- Plan UI mockup

### Deliverable
- 10 emails analyzed and stored
- System architecture documented

---

## Week 3: Telegram Integration + Draft Replies (Apr 5-11)

> **Pivot (2026-04-24):** Replaced "basic web interface" goal with a Telegram-only UX. Webhook into existing FastAPI, single-user auth, approve-before-send for replies, push notifications for high-priority emails. Story breakdown lives in `docs/PROGRESS.md`. The Flask + HTML samples below remain as historical reference only — they are not implemented.

### Goals
- ✅ Generate draft replies
- ✅ Telegram bot as sole user interface (replaces web UI)
- ✅ Push notifications for important emails

### Tasks

**Day 1-3: Draft Reply Generation**
Create `src/ai/reply_generator.py`:
```python
def generate_replies(email_data, thread_context=None):
    tones = ['professional', 'friendly', 'brief']
    replies = {}
    
    for tone in tones:
        prompt = build_reply_prompt(email_data, tone, thread_context)
        reply = call_claude(prompt)
        replies[tone] = reply
    
    return replies

def build_reply_prompt(email_data, tone, thread_context):
    tone_instructions = {
        'professional': "formal, detailed, and polite. Use professional language.",
        'friendly': "warm, conversational, and casual. Sound like a friend.",
        'brief': "concise and to-the-point. Keep it under 3 sentences."
    }
    
    context = f"\nPrevious conversation:\n{thread_context}" if thread_context else ""
    
    return f"""Generate a {tone} email reply.

ORIGINAL EMAIL:
From: {email_data['sender']}
Subject: {email_data['subject']}
Body: {email_data['body']}
{context}

Write a reply that is {tone_instructions[tone]}

Address all questions and requests in the email.
Sound natural and human.

REPLY:"""
```

**Day 4-5: Basic Web Interface**
Create `src/ui/app.py`:
```python
from flask import Flask, render_template, jsonify, request
from database.db import Database
from ai.reply_generator import generate_replies

app = Flask(__name__)
db = Database()

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/emails')
def get_emails():
    emails = db.get_recent_emails(limit=50)
    return jsonify(emails)

@app.route('/api/email/<int:email_id>')
def get_email_detail(email_id):
    email = db.get_email_by_id(email_id)
    return jsonify(email)

@app.route('/api/generate-replies/<int:email_id>', methods=['POST'])
def generate_replies_endpoint(email_id):
    email = db.get_email_by_id(email_id)
    replies = generate_replies(email)
    
    # Store drafts
    for tone, text in replies.items():
        db.insert_draft_reply(email_id, tone, text)
    
    return jsonify(replies)

if __name__ == '__main__':
    app.run(debug=True)
```

Create `src/ui/templates/dashboard.html`:
```html
<!DOCTYPE html>
<html>
<head>
    <title>Email Assistant</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .email-list { max-width: 800px; }
        .email-item { 
            border: 1px solid #ddd; 
            padding: 15px; 
            margin-bottom: 10px;
            cursor: pointer;
        }
        .email-item:hover { background-color: #f5f5f5; }
        .category-badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 12px;
            margin-left: 10px;
        }
    </style>
</head>
<body>
    <h1>📧 Email Assistant</h1>
    <div id="email-list" class="email-list"></div>
    
    <script>
        async function loadEmails() {
            const response = await fetch('/api/emails');
            const emails = await response.json();
            
            const listDiv = document.getElementById('email-list');
            listDiv.innerHTML = emails.map(email => `
                <div class="email-item" onclick="viewEmail(${email.id})">
                    <strong>${email.sender}</strong>
                    <span class="category-badge">${email.category}</span>
                    <br>
                    <em>${email.subject}</em>
                    <p>${email.ai_summary}</p>
                </div>
            `).join('');
        }
        
        function viewEmail(id) {
            window.location.href = `/email/${id}`;
        }
        
        loadEmails();
    </script>
</body>
</html>
```

**Day 6-7: Prompt Testing**
- Test different prompt variations
- Measure reply quality
- Optimize token usage
- Document best prompts

### Deliverable
- Telegram bot as primary interface (commands + push notifications + approve-before-send)
- Can generate 3-tone replies via `/reply <id>` flow
- Prompt templates documented

---

## Week 4: External Data + Knowledge (Apr 12-18)

### Goals
- ✅ Calendar integration working
- ✅ Meeting detection accurate
- ✅ Can create calendar events

### Tasks

**Day 1-3: Calendar API Integration**
Add to `src/auth/gmail_auth.py`:
```python
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar'
]

def get_calendar_service():
    creds = get_credentials()
    return build('calendar', 'v3', credentials=creds)
```

Create `src/calendar/event_creator.py`:
```python
from datetime import datetime, timedelta
from googleapiclient.errors import HttpError

def create_calendar_event(service, event_details):
    event = {
        'summary': event_details['title'],
        'description': event_details.get('description', ''),
        'start': {
            'dateTime': event_details['start_time'],
            'timeZone': 'Asia/Jerusalem',
        },
        'end': {
            'dateTime': event_details['end_time'],
            'timeZone': 'Asia/Jerusalem',
        },
        'attendees': [
            {'email': email} for email in event_details.get('attendees', [])
        ],
    }
    
    try:
        created_event = service.events().insert(
            calendarId='primary',
            body=event
        ).execute()
        
        return created_event['id']
    except HttpError as error:
        print(f'An error occurred: {error}')
        return None
```

**Day 4-5: Meeting Detection**
Create `src/ai/meeting_detector.py`:
```python
import re
from dateutil import parser
from datetime import datetime, timedelta

def detect_meeting_request(email_body):
    """Use Claude to detect meeting requests and extract details"""
    
    prompt = f"""Analyze this email for meeting/call requests.

EMAIL:
{email_body}

If this email contains a meeting request, respond with JSON:
{{
  "is_meeting_request": true,
  "title": "meeting title/subject",
  "proposed_times": ["2024-03-20 14:00", "2024-03-21 10:00"],
  "duration_minutes": 60,
  "participants": ["email@example.com"],
  "location": "Zoom/Office/Address",
  "agenda": "brief description"
}}

If no meeting request, respond with:
{{"is_meeting_request": false}}
"""
    
    response = call_claude(prompt)
    return parse_meeting_json(response)

def parse_natural_date(date_string):
    """Convert natural language dates to datetime"""
    # "next Tuesday at 3pm"
    # "tomorrow morning"
    # "March 20th at 2:30pm"
    
    try:
        return parser.parse(date_string)
    except:
        return None
```

**Day 6-7: Integration & Testing**
- Connect meeting detection to email processing
- Test calendar event creation
- Add UI for calendar events
- Handle edge cases

### Deliverable
- Meetings detected from emails
- Calendar events created successfully
- End-to-end flow working

---

## Week 5: Agentic Workflows (Apr 19-25)

### Goals
- ✅ System makes autonomous decisions
- ✅ Follow-up tracking implemented
- ✅ Smart bulk actions working

### Tasks

**Day 1-3: Decision Agent**
Create `src/ai/decision_agent.py`:
```python
def should_reply(email_data, user_context):
    """Decide if email needs a reply"""
    
    prompt = f"""Analyze if this email requires a response from the user.

EMAIL:
From: {email_data['sender']}
Subject: {email_data['subject']}
Body: {email_data['body']}
Category: {email_data['category']}

USER CONTEXT:
- Has auto-archive enabled for: {user_context.get('auto_archive_categories', [])}
- Typical response time: {user_context.get('avg_response_time', 'within 24 hours')}

Decision needed:
1. Does this require a response? (yes/no)
2. How urgent? (low/medium/high)
3. Suggested action? (reply/schedule/forward/archive)
4. When to follow up if no response? (days)

Respond in JSON format."""

    response = call_claude(prompt)
    return parse_decision(response)

def prioritize_inbox(emails):
    """Sort emails by urgency and importance"""
    
    scored_emails = []
    for email in emails:
        score = calculate_priority_score(email)
        scored_emails.append((email, score))
    
    return sorted(scored_emails, key=lambda x: x[1], reverse=True)

def calculate_priority_score(email):
    """Calculate priority based on multiple factors"""
    score = 0
    
    # Urgency
    if email['urgency_score'] >= 8:
        score += 50
    elif email['urgency_score'] >= 5:
        score += 25
    
    # Action required
    if email['action_required'] == 'Reply':
        score += 30
    elif email['action_required'] == 'Schedule':
        score += 40
    
    # Sender importance (learn from past interactions)
    if is_important_sender(email['sender']):
        score += 20
    
    # Time since received
    hours_old = get_hours_since_received(email)
    if hours_old > 48:
        score += 15
    
    return score
```

**Day 4-5: Follow-up System**
Create `src/followup/tracker.py`:
```python
from datetime import datetime, timedelta

def create_followup(email_id, days=3, reason=None):
    """Set reminder to follow up on email"""
    remind_at = datetime.now() + timedelta(days=days)
    
    db.insert_followup(email_id, remind_at, reason)

def check_pending_followups():
    """Get emails that need follow-up"""
    followups = db.get_pending_followups()
    
    notifications = []
    for followup in followups:
        email = db.get_email_by_id(followup['email_id'])
        
        notifications.append({
            'email': email,
            'reason': followup['reason'],
            'overdue_days': (datetime.now() - followup['remind_at']).days
        })
    
    return notifications

def auto_snooze_email(email_id, until_date):
    """Snooze email until specific date"""
    db.update_followup_snooze(email_id, until_date)
```

**Day 6-7: Bulk Actions**
- Implement "archive all newsletters"
- Add "reply to all in category"
- Create action templates
- Test autonomous workflows

### Deliverable
- Agent makes smart decisions
- Follow-ups tracked automatically
- Bulk actions working

---

## Week 6: UI & Demo (Apr 26-May 2)

### Goals
- ✅ Production-ready UI
- ✅ Demo video recorded
- ✅ Elevator pitch written

### Tasks

**Day 1-3: UI Polish**
- Upgrade to React (optional)
- Add animations and transitions
- Improve mobile responsiveness
- Add loading states
- Implement error handling UI

**Day 4-5: Demo Preparation**
Write demo script:
```
DEMO SCRIPT (3-5 minutes)

[Scene 1: The Problem - 30 seconds]
"I get 50+ emails a day. Reading, categorizing, and responding takes 1-2 hours daily."

[Scene 2: The Solution - 30 seconds]
"I built an AI-powered email assistant using Claude API and Gmail integration."

[Scene 3: Demo - 3 minutes]
1. Show inbox (50 unread emails)
2. Click "Analyze Inbox" → AI processes all emails
3. Show categorized view with summaries
4. Click email → see 3 draft replies
5. Edit and send reply
6. Detect meeting → create calendar event with 1 click
7. Show follow-up tracking

[Scene 4: Results - 30 seconds]
"Email processing time: 1.5 hours → 15 minutes (90% reduction)"

[Scene 5: Tech Stack - 30 seconds]
"Built with: Python, Flask, Gmail API, Claude API, SQLite"
"Skills learned: API integration, prompt engineering, agentic workflows"
```

**Day 6-7: Recording & Editing**
- Record demo video
- Add captions
- Upload to YouTube
- Write elevator pitch

### Deliverable
- Polished UI
- Professional demo video
- Elevator pitch ready

---

## Week 7: Documentation & Delivery (May 3-9)

### Goals
- ✅ Complete documentation
- ✅ Code cleaned and commented
- ✅ Ready for submission

### Tasks

**Day 1-2: README Documentation**
Create comprehensive README.md:
```markdown
# Smart Email Assistant

AI-powered Gmail assistant that analyzes emails, generates replies, and automates inbox management.

## Features
- 📧 Email analysis with Claude AI
- ✍️ Smart reply generation (3 tones)
- 📅 Calendar event detection & creation
- 🏷️ Auto-categorization
- ⏰ Follow-up tracking
- 🎯 Priority inbox

## Tech Stack
- Backend: Python, Flask, SQLite
- APIs: Gmail, Calendar, Claude
- Frontend: HTML/CSS/JavaScript (or React)

## Setup Instructions
1. Clone repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up Gmail API credentials
4. Add Claude API key to .env
5. Run: `python src/main.py`

## Demo
[YouTube video link]

## Architecture
[System diagram]

## Skills Learned
- API integration (Gmail, Calendar)
- LLM prompt engineering
- Agentic workflow design
- Full-stack development
```

**Day 3-4: Code Cleanup**
- Add docstrings to all functions
- Remove debug print statements
- Organize imports
- Format code (black, autopep8)
- Remove unused code

**Day 5-6: requirements.txt & .env**
Create `requirements.txt`:
```
google-api-python-client==2.88.0
google-auth-httplib2==0.1.0
google-auth-oauthlib==1.0.0
anthropic==0.25.0
flask==3.0.0
python-dotenv==1.0.0
python-dateutil==2.8.2
```

Create `.env.example`:
```
ANTHROPIC_API_KEY=your_key_here
GMAIL_CREDENTIALS_PATH=credentials.json
DATABASE_PATH=email_assistant.db
```

**Day 7: Final Checks**
- Test full workflow end-to-end
- Fix any bugs
- Final commit
- Submit project

### Deliverable
- Complete, documented project
- Ready for showcase
- Submitted on time

---

## Success Metrics & Evaluation

### Technical Metrics
- [ ] Successfully authenticates with Gmail API
- [ ] Processes 50+ emails in under 5 seconds
- [ ] AI analysis accuracy > 80%
- [ ] Reply generation acceptance rate > 70%
- [ ] Calendar event detection accuracy > 90%
- [ ] Zero crashes during demo
- [ ] Code coverage > 60% (if tests written)

### Learning Metrics
- [ ] Understands OAuth 2.0 flow
- [ ] Can write effective LLM prompts
- [ ] Knows how to handle API rate limits
- [ ] Can design database schemas
- [ ] Understands agentic workflows
- [ ] Can build full-stack applications

### Portfolio Metrics
- [ ] GitHub repo has README, documentation
- [ ] Demo video is professional quality
- [ ] Can explain architecture clearly
- [ ] Can discuss technical decisions
- [ ] Project is showcaseable to employers

---

## Risk Management

### Technical Risks

**Risk: Gmail API quota exceeded**
- Mitigation: Implement caching, pagination
- Fallback: Request quota increase from Google

**Risk: Claude API costs too high**
- Mitigation: Use prompt caching, batch requests
- Fallback: Switch to Claude Haiku for lower costs

**Risk: OAuth authentication complex**
- Mitigation: Follow official tutorials closely
- Fallback: Use example code from Google docs

**Risk: Prompt engineering takes longer than expected**
- Mitigation: Start with simple prompts, iterate
- Fallback: Use proven templates from documentation

### Scope Risks

**Risk: Feature creep**
- Mitigation: Strict adherence to MoSCoW priorities
- Fallback: Cut COULD HAVE features

**Risk: UI takes too long**
- Mitigation: Keep Week 1-5 UI minimal
- Fallback: Polish in Week 6 only

---

## Resources & References

### Documentation
- Gmail API: https://developers.google.com/gmail/api
- Calendar API: https://developers.google.com/calendar
- Claude API: https://docs.anthropic.com/
- OAuth 2.0: https://developers.google.com/identity/protocols/oauth2

### Tutorials
- Gmail Python Quickstart: https://developers.google.com/gmail/api/quickstart/python
- Flask Tutorial: https://flask.palletsprojects.com/tutorial/
- SQLite with Python: https://docs.python.org/3/library/sqlite3.html

### Tools
- Postman (API testing)
- DB Browser for SQLite
- VS Code with Python extension
- Git/GitHub

---

## Appendix: Example Prompts

### Email Analysis Prompt
```
Analyze this email and extract key information.

EMAIL:
From: {sender}
Subject: {subject}
Body: {body}

Provide JSON output:
{
  "summary": "brief summary",
  "category": "Work|Personal|etc",
  "sentiment": "Urgent|Casual|Formal",
  "action": "Reply|Schedule|Archive",
  "urgency": 1-10,
  "key_info": {
    "dates": [],
    "people": [],
    "deadlines": [],
    "questions": []
  }
}
```

### Reply Generation Prompt
```
Generate a {tone} reply to this email.

ORIGINAL EMAIL:
{email_content}

TONE: {professional|friendly|brief}

Instructions for {tone}:
- Professional: Formal, detailed, polite
- Friendly: Warm, conversational, casual
- Brief: Under 3 sentences, direct

Address all points raised.
Maintain natural, human tone.

REPLY:
```

### Meeting Detection Prompt
```
Detect if this email contains a meeting request.

EMAIL:
{body}

Extract:
- Is this a meeting request? (yes/no)
- Proposed date/time
- Duration
- Participants
- Location (Zoom/Office/etc)
- Agenda

JSON format:
{
  "is_meeting": true/false,
  "details": {...}
}
```

---

## Contact & Support

**Project Owner:** [Your Name]  
**Timeline:** March 15 - May 9, 2026  
**Status:** In Progress - Week 1

For questions about this PRD or project, refer to:
- GitHub Issues
- Weekly check-ins with mentor
- Claude Code assistance

---

**Last Updated:** Week 1 - March 15, 2026  
**Version:** 1.0
