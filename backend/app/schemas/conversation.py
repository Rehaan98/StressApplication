"""
Conversation bot schemas — separate from /voice/* so existing clients are unaffected.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ConversationStartRequest(BaseModel):
    user_name: Optional[str] = Field(default=None, description="Optional display name for a warmer greeting")


class ConversationStartResponse(BaseModel):
    session_id: str
    reply: str
    activity: str = "supportive_conversation"


class StressContextPayload(BaseModel):
    """Optional stress estimate from the EXISTING pipelines.

    Accepts 0-1 or 0-100 scores; everything optional. The bot never invents
    these values — omit the whole object when detection is unavailable.
    """

    stress_score: Optional[float] = Field(default=None, description="Stress score, 0-1 or 0-100")
    stress_level: Optional[str] = Field(default=None, description="Low | Moderate | High | Severe | Very High")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    trend: Optional[str] = Field(default=None, description="increasing | decreasing | stable")
    voice_indicators: Dict[str, Any] = Field(default={})
    webcam_indicators: Dict[str, Any] = Field(default={})


class ConversationMessageRequest(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1, max_length=2000, description="User message (typed or speech-to-text)")
    stress_context: Optional[StressContextPayload] = Field(default=None)
    use_llm: Optional[bool] = Field(default=True, description="Allow LLM reply when configured; offline fallback otherwise")


class ConversationIntervention(BaseModel):
    id: str = ""
    category: str = ""
    title: str = ""
    summary: str = ""
    protocol: List[str] = []
    evidence_base: str = ""
    difficulty: str = ""
    duration_min: int = 0
    relevance_score: float = 0.0


class ConversationMessageResponse(BaseModel):
    session_id: str
    reply: str
    activity: str = "supportive_conversation"
    activity_title: str = ""
    activity_summary: str = ""
    activity_steps: List[str] = []
    activity_check_in: str = ""
    activity_alternative: str = ""
    suggested_action: str = ""
    safety_notice: Optional[str] = None
    is_safety: bool = False
    language_understanding: Dict[str, Any] = {}
    stress_adaptation: Dict[str, Any] = {}
    interventions: List[Dict[str, Any]] = []


class ConversationHistoryResponse(BaseModel):
    session_id: str
    turns: List[Dict[str, str]] = []
    facts: Dict[str, Any] = {}
    last_activity: Optional[str] = None
    turn_count: int = 0
    tone: str = "gentle"
    exercise_status: Dict[str, Any] = {}


class ConversationEndResponse(BaseModel):
    session_id: str
    reply: str
    ended: bool = True
