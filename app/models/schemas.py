from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class Email(BaseModel):
    id: str
    thread_id: Optional[str] = None
    sender: Optional[str] = None
    subject: Optional[str] = None
    date: Optional[str] = None
    snippet: str = ""
    body: Optional[str] = None


class AnalysisResult(BaseModel):
    summary: str
    category: str  # Work, Personal, Newsletter, Finance, Travel, Shopping, Other
    sentiment: str  # Urgent, Casual, Formal
    action_required: str  # Reply, Schedule, Read, Archive, Flag
    urgency_score: int  # 1-10
    key_dates: list[str] = []
    key_people: list[str] = []


class EmailWithAnalysis(BaseModel):
    email: Email
    analysis: Optional[AnalysisResult] = None


class DraftReply(BaseModel):
    email_id: str
    tone: str  # professional, friendly, brief
    draft_text: str
    was_sent: bool = False
    sent_at: Optional[datetime] = None
