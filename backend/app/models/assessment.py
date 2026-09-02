"""
Stress Assessment SQLAlchemy Model
"""

from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime, JSON
from backend.app.core.database import Base

class StressAssessment(Base):
    __tablename__ = "stress_assessments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    
    # PSS-10 Items
    pss_q1 = Column(Integer, nullable=False)
    pss_q2 = Column(Integer, nullable=False)
    pss_q3 = Column(Integer, nullable=False)
    pss_q4 = Column(Integer, nullable=False)
    pss_q5 = Column(Integer, nullable=False)
    pss_q6 = Column(Integer, nullable=False)
    pss_q7 = Column(Integer, nullable=False)
    pss_q8 = Column(Integer, nullable=False)
    pss_q9 = Column(Integer, nullable=False)
    pss_q10 = Column(Integer, nullable=False)
    total_pss = Column(Integer, nullable=False)
    
    # Physiological Markers
    heart_rate = Column(Float, nullable=False)
    hrv_sdnn = Column(Float, nullable=False)
    sleep_hours = Column(Float, nullable=False)
    sleep_efficiency = Column(Float, nullable=False)
    physical_activity_min = Column(Float, nullable=False)
    
    # Workload & Cognitive Markers
    work_hours = Column(Float, nullable=False)
    screen_time_hours = Column(Float, nullable=False)
    breaks_per_day = Column(Integer, nullable=False)
    sentiment_score = Column(Float, nullable=False)
    anxiety_score = Column(Float, nullable=False)
    
    notes = Column(String(1000), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
