from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class StudentAnalytics(BaseModel):
    student_id: int
    username: str
    email: str
    view_count: int
    last_viewed: Optional[str]
    has_viewed: bool

class ResourceInfo(BaseModel):
    id: int
    title: str
    resource_type: str
    session_title: str
    course_title: Optional[str]

class AnalyticsSummary(BaseModel):
    total_views: int
    unique_viewers: int
    total_students: int
    view_percentage: float

class ResourceAnalyticsResponse(BaseModel):
    resource: ResourceInfo
    summary: AnalyticsSummary
    student_analytics: List[StudentAnalytics]

class ResourceSummary(BaseModel):
    resource_id: int
    title: str
    resource_type: str
    total_views: int
    unique_viewers: int
    uploaded_at: Optional[str]

class SessionInfo(BaseModel):
    id: int
    title: str

class SessionResourceAnalyticsResponse(BaseModel):
    session: SessionInfo
    resources: List[ResourceSummary]

class TopResource(BaseModel):
    resource_id: int
    title: str
    resource_type: str
    session_title: str
    total_views: int
    unique_viewers: int

class TopResourcesResponse(BaseModel):
    top_resources: List[TopResource]

class DailyTrend(BaseModel):
    date: str
    views: int
    unique_viewers: int

class TrendPeriod(BaseModel):
    start_date: str
    end_date: str
    days: int

class ResourceTrendsResponse(BaseModel):
    resource: dict
    period: TrendPeriod
    trends: List[DailyTrend]