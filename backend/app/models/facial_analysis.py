"""
Facial Expression Analysis SQLAlchemy Model
"""

from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime, JSON
from backend.app.core.database import Base

class FacialAnalysis(Base):
    __tablename__ = "facial_analyses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)

    dominant_emotion = Column(String(50), nullable=False)
    emotion_probabilities = Column(JSON, nullable=False)
    stress_score = Column(Float, nullable=False)
    stress_level = Column(String(50), nullable=False)  # Low, Moderate, High, Severe
    confidence_score = Column(Float, nullable=False)
    model = Column(String(50), nullable=False, default="ferplus-fer2013")
    face_detected = Column(Integer, nullable=False, default=1)
    num_faces = Column(Integer, nullable=False, default=1)
    source = Column(String(50), nullable=False, default="webcam")

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
