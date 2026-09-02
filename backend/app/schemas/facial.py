"""
Facial Expression Analysis Pydantic Schemas
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class FacialAnalyzeRequest(BaseModel):
    image: str = Field(..., description="Base64-encoded JPEG/PNG image (raw, no data URI prefix)")
    source: str = "webcam"

class FacialAnalyzeResponse(BaseModel):
    id: str
    face_detected: bool
    num_faces: int
    dominant_emotion: Optional[str] = None
    emotion_probabilities: Dict[str, float]
    stress_score: float
    stress_level: str
    confidence_score: float
    model: str
    processing_ms: float
    interventions: List[Dict[str, Any]] = []

class FacialHistoryItem(BaseModel):
    id: str
    dominant_emotion: str
    emotion_probabilities: Dict[str, float]
    stress_score: float
    stress_level: str
    confidence_score: float
    source: str
    created_at: datetime

    class Config:
        from_attributes = True

class FacialHistoryResponse(BaseModel):
    items: List[FacialHistoryItem]
    total: int
    current_stress_score: Optional[float] = None
    current_stress_level: Optional[str] = None
