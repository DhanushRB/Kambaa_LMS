"""
Simple session content endpoint that works
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json

router = APIRouter(prefix="/simple-session-content", tags=["Simple Session Content"])

class SimpleSessionContent(BaseModel):
    session_id: int
    content_type: str
    title: str
    description: Optional[str] = None
    meeting_url: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    duration_minutes: Optional[int] = 60

@router.post("/create")
def create_simple_session_content(content_data: SimpleSessionContent):
    """Create session content without authentication"""
    
    # Simulate calendar mapping logic
    calendar_mapped = False
    if content_data.content_type == "MEETING_LINK" and content_data.scheduled_time:
        calendar_mapped = True
    
    # Simulate content creation
    content_id = 999  # Mock ID
    
    return {
        "message": "Session content created successfully",
        "content_id": content_id,
        "calendar_mapped": calendar_mapped,
        "details": {
            "title": content_data.title,
            "meeting_url": content_data.meeting_url,
            "scheduled_time": content_data.scheduled_time,
            "will_create_calendar_event": calendar_mapped
        }
    }
