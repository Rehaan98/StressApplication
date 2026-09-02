"""
Explainability Pydantic Schemas
"""

from typing import List, Dict, Any
from pydantic import BaseModel

class FeatureImpact(BaseModel):
    feature: str
    shap_value: float
    impact: str

class ExplainabilityResponse(BaseModel):
    prediction_id: str
    predicted_class: str
    top_drivers: List[FeatureImpact]
    lime_rules: List[Dict[str, Any]]
