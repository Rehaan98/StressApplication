"""
Prediction Result SQLAlchemy Model
"""

from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime, JSON
from backend.app.core.database import Base

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    assessment_id = Column(String(36), ForeignKey("stress_assessments.id"), index=True, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    
    predicted_class_id = Column(Integer, nullable=False)
    stress_level = Column(String(50), nullable=False) # Low, Moderate, High, Severe
    confidence_score = Column(Float, nullable=False)
    class_probabilities = Column(JSON, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
