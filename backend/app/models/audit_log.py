"""
System Audit Log SQLAlchemy Model
"""

from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, DateTime, JSON
from backend.app.core.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True) # e.g. LOGIN, ASSESSMENT_CREATED, PREDICTION_RUN, ADMIN_ACTION
    ip_address = Column(String(45), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
