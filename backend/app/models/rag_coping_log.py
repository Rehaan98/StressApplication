"""
RAG Coping Log SQLAlchemy Model
"""

from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, JSON
from backend.app.core.database import Base

class RAGCopingLog(Base):
    __tablename__ = "rag_coping_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    prediction_id = Column(String(36), ForeignKey("predictions.id"), nullable=True)
    
    query_text = Column(String(500), nullable=True)
    retrieved_interventions = Column(JSON, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
