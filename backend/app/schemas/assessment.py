"""
Stress Assessment Pydantic Schemas

New: Real-time fitness tracker data ingestion support.
Users can push HR, HRV, sleep, and activity data from wearable devices
(Apple Health, Google Fit, Fitbit, Garmin, etc.) for immediate use
in stress assessments and ML predictions.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, model_validator

# Neutral default used for unanswered questionnaire items
PSS_DEFAULT = 2

# Neutral defaults for physiological / workload fields
FIELD_DEFAULTS = {
    "heart_rate": 72.0,
    "hrv_sdnn": 55.0,
    "sleep_hours": 7.0,
    "sleep_efficiency": 85.0,
    "physical_activity_min": 30.0,
    "work_hours": 8.0,
    "screen_time_hours": 6.0,
    "breaks_per_day": 4,
    "sentiment_score": 0.2,
    "anxiety_score": 4.0,
}

class StressAssessmentCreate(BaseModel):
    """
    All fields are optional — users may skip questions they prefer not to answer.
    Unanswered items are filled server-side with neutral defaults so the ML
    pipeline always receives a complete feature vector.
    """
    # PSS-10 responses (0-4), optional
    pss_q1: Optional[int] = Field(None, ge=0, le=4)
    pss_q2: Optional[int] = Field(None, ge=0, le=4)
    pss_q3: Optional[int] = Field(None, ge=0, le=4)
    pss_q4: Optional[int] = Field(None, ge=0, le=4)
    pss_q5: Optional[int] = Field(None, ge=0, le=4)
    pss_q6: Optional[int] = Field(None, ge=0, le=4)
    pss_q7: Optional[int] = Field(None, ge=0, le=4)
    pss_q8: Optional[int] = Field(None, ge=0, le=4)
    pss_q9: Optional[int] = Field(None, ge=0, le=4)
    pss_q10: Optional[int] = Field(None, ge=0, le=4)

    # Physiological markers, optional
    heart_rate: Optional[float] = Field(None, ge=40, le=160)
    hrv_sdnn: Optional[float] = Field(None, ge=10, le=150)
    sleep_hours: Optional[float] = Field(None, ge=1, le=14)
    sleep_efficiency: Optional[float] = Field(None, ge=20, le=100)
    physical_activity_min: Optional[float] = Field(None, ge=0, le=300)

    # Workload & Cognitive, optional
    work_hours: Optional[float] = Field(None, ge=0, le=20)
    screen_time_hours: Optional[float] = Field(None, ge=0, le=20)
    breaks_per_day: Optional[int] = Field(None, ge=0, le=20)
    sentiment_score: Optional[float] = Field(None, ge=-1.0, le=1.0)
    anxiety_score: Optional[float] = Field(None, ge=0.0, le=10.0)

    notes: Optional[str] = None

    # Real-time fitness tracker data (optional)
    # Users can push real-time physiological data from wearable devices
    # Apple Health, Google Fit, Fitbit, Garmin, etc.
    tracker_heart_rate: Optional[float] = Field(
        None, ge=40, le=160, description="Real-time heart rate from fitness tracker (BPM)"
    )
    tracker_hrv_sdnn: Optional[float] = Field(
        None, ge=10, le=150, description="Real-time HRV SDNN from fitness tracker (ms)"
    )
    tracker_sleep_hours: Optional[float] = Field(
        None, ge=1, le=14, description="Real-time sleep hours from fitness tracker"
    )
    tracker_sleep_efficiency: Optional[float] = Field(
        None, ge=20, le=100, description="Real-time sleep efficiency from fitness tracker (%)"
    )
    tracker_physical_activity_min: Optional[float] = Field(
        None, ge=0, le=300, description="Real-time physical activity minutes from fitness tracker"
    )
    tracker_work_hours: Optional[float] = Field(
        None, ge=0, le=24, description="Real-time work hours from fitness tracker"
    )
    tracker_screen_time_hours: Optional[float] = Field(
        None, ge=0, le=24, description="Real-time screen time hours from fitness tracker"
    )
    tracker_breaks_per_day: Optional[int] = Field(
        None, ge=0, le=20, description="Real-time breaks per day from fitness tracker"
    )
    tracker_sentiment_score: Optional[float] = Field(
        None, ge=-1.0, le=1.0, description="Real-time sentiment score from fitness tracker"
    )
    tracker_anxiety_score: Optional[float] = Field(
        None, ge=0.0, le=10.0, description="Real-time anxiety score from fitness tracker"
    )

    @model_validator(mode="after")
    def fill_neutral_defaults(self):
        """Fill unanswered items with neutral values so the ML pipeline is complete."""
        for i in range(1, 11):
            key = f"pss_q{i}"
            if getattr(self, key) is None:
                setattr(self, key, PSS_DEFAULT)
        for key, default in FIELD_DEFAULTS.items():
            if getattr(self, key) is None:
                setattr(self, key, default)
        return self

class StressAssessmentResponse(BaseModel):
    id: str
    user_id: str
    pss_q1: Optional[int] = None
    pss_q2: Optional[int] = None
    pss_q3: Optional[int] = None
    pss_q4: Optional[int] = None
    pss_q5: Optional[int] = None
    pss_q6: Optional[int] = None
    pss_q7: Optional[int] = None
    pss_q8: Optional[int] = None
    pss_q9: Optional[int] = None
    pss_q10: Optional[int] = None
    total_pss: int
    heart_rate: Optional[float] = None
    hrv_sdnn: Optional[float] = None
    sleep_hours: Optional[float] = None
    sleep_efficiency: Optional[float] = None
    physical_activity_min: Optional[float] = None
    work_hours: Optional[float] = None
    screen_time_hours: Optional[float] = None
    breaks_per_day: Optional[int] = None
    sentiment_score: Optional[float] = None
    anxiety_score: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
