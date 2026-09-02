"""
RAG Coping Interventions Pydantic Schemas
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class RAGQueryRequest(BaseModel):
    prediction_id: Optional[str] = None
    query_text: Optional[str] = ""
    top_k: int = 3
    emotion: Optional[str] = ""

class InterventionItem(BaseModel):
    id: str
    category: str
    title: str
    summary: str
    protocol: List[str]
    evidence_base: str
    difficulty: str
    duration_min: int
    relevance_score: float

class RAGCopingResponse(BaseModel):
    query_text: str
    stress_level: Optional[str] = None
    interventions: List[InterventionItem]
