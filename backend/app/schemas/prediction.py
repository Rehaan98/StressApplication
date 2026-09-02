"""
Prediction Pydantic Schemas
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel

class PredictionRequest(BaseModel):
    assessment_id: str

class PredictionResponse(BaseModel):
    id: str
    assessment_id: str
    user_id: str
    predicted_class_id: int
    stress_level: str # Low, Moderate, High, Severe
    confidence_score: float
    class_probabilities: Dict[str, float]
    created_at: datetime
    
    # Nested XAI & RAG payloads if returned together
    shap_explanation: Optional[Dict[str, Any]] = None
    lime_explanation: Optional[Dict[str, Any]] = None
    rag_interventions: Optional[List[Dict[str, Any]]] = None

    class Config:
        from_attributes = True
