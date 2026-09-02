"""
Explainability Log SQLAlchemy Model (SHAP & LIME)
"""

from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, JSON
from backend.app.core.database import Base

class ExplainabilityLog(Base):
    __tablename__ = "explainability_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prediction_id = Column(String(36), ForeignKey("predictions.id"), index=True, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    
    shap_top_drivers = Column(JSON, nullable=False)
    lime_rules = Column(JSON, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
