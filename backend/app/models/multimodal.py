"""
Multimodal Assessment SQLAlchemy Model

Persists one unified assessment: the fused estimate plus each contributing
modality result. Never stores raw audio or webcam frames — only references
(assessment / facial reading ids), transcripts, and numeric results.
"""

from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Float, ForeignKey, DateTime, JSON, Text
from backend.app.core.database import Base

class MultimodalAssessment(Base):
    __tablename__ = "multimodal_assessments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)

    # Input references (no raw audio/image stored)
    assessment_id = Column(String(36), ForeignKey("stress_assessments.id"), nullable=True)
    facial_reading_id = Column(String(36), ForeignKey("facial_analyses.id"), nullable=True)
    voice_transcript = Column(Text, nullable=True)

    # Fused output
    overall_score = Column(Float, nullable=False)  # 0-1
    overall_category = Column(String(50), nullable=False)  # Low/Moderate/High/Severe/Uncertain
    confidence = Column(Float, nullable=False)  # 0-1
    fusion_method = Column(String(100), nullable=False, default="confidence-weighted-provisional-v1")
    fusion_version = Column(String(20), nullable=False, default="1.0")

    available_modalities = Column(JSON, nullable=False, default=list)
    missing_modalities = Column(JSON, nullable=False, default=list)
    modality_results = Column(JSON, nullable=False, default=dict)
    contributing_factors = Column(JSON, nullable=False, default=list)
    limitations = Column(JSON, nullable=False, default=list)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
