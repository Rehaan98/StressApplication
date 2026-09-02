"""
Analytics Pydantic Schemas
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class UserStressTrend(BaseModel):
    date: str
    stress_level: str
    total_pss: int
    heart_rate: float
    hrv_sdnn: float
    sleep_hours: float
    confidence_score: float

class AnalyticsOverviewResponse(BaseModel):
    total_assessments: int
    latest_stress_level: str
    average_pss_score: float
    average_hrv_sdnn: float
    average_sleep_hours: float
    stress_distribution: Dict[str, int]
    timeline_trends: List[UserStressTrend]
    total_facial_analyses: Optional[int] = 0
    latest_facial_emotion: Optional[str] = None
    latest_facial_stress_level: Optional[str] = None
    latest_facial_stress_score: Optional[float] = None
    facial_stress_distribution: Optional[Dict[str, int]] = None

class AdminAnalyticsResponse(BaseModel):
    total_users: int
    total_assessments: int
    total_predictions: int
    total_facial_analyses: Optional[int] = 0
    system_stress_breakdown: Dict[str, int]
    active_users_7d: int
    model_performance_summary: Dict[str, Any]
