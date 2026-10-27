"""
Voice Stress Analysis Schemas
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class VoiceAnalyzeRequest(BaseModel):
    audio_base64: str = Field(..., description="Base64-encoded audio (WAV preferred, webm/opus also accepted)")
    sample_rate: int = Field(default=16000, ge=8000, le=48000, description="Audio sample rate in Hz")
    duration: float = Field(default=0.5, ge=0.1, le=180.0, description="Audio duration in seconds")
    session_id: Optional[str] = Field(default=None, description="Optional client session id")
    transcript: Optional[str] = Field(default=None, description="Optional client-side speech-to-text transcript")


class VoiceIntervention(BaseModel):
    id: str = ""
    category: str = ""
    title: str = ""
    summary: str = ""
    protocol: List[str] = []
    evidence_base: str = ""
    difficulty: str = ""
    duration_min: int = 0
    relevance_score: float = 0.0


class VoiceAnalyzeResponse(BaseModel):
    stress_score: float = Field(..., ge=0.0, le=1.0, description="Combined stress score 0.0-1.0 (voice tone + words)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the stress estimate")
    stress_level: str = Field(..., description="Low, Moderate, or High")
    voice_features: Dict[str, float] = Field(
        default={},
        description="Extracted voice features (pitch, energy, etc.)",
    )
    session_id: str = Field(..., description="Current assessment session ID")
    voice_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Acoustic voice-tone score")
    text_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Spoken-words score")
    voice_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Confidence in the voice-tone score")
    text_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Confidence in the words score")
    transcript: Optional[str] = Field(default=None, description="Echo of the transcript used")
    text_keywords: List[str] = Field(default=[], description="Stress keywords found in words")
    emotion_hint: Optional[str] = Field(default=None, description="Emotion hint from words (anger/fear/sadness/...)")
    explanation: Optional[str] = Field(default=None, description="Plain-language reason for the score")
    interventions: List[VoiceIntervention] = Field(default=[], description="Suggested coping treatments")
    insufficient_evidence: bool = Field(
        default=False,
        description="True when neither audio nor words gave usable evidence — score is a neutral placeholder",
    )
    voice_available: bool = Field(
        default=True, description="False when no clear speech was found in the audio"
    )
    audio_level: Optional[str] = Field(
        default=None, description="Recording level: silent | very_quiet | quiet | normal | loud"
    )
    quiet_warning: Optional[str] = Field(
        default=None, description="Guidance shown when the voice was too quiet for a full tone reading"
    )


class VoiceSessionStartRequest(BaseModel):
    session_id: str = Field(..., description="Unique session identifier")
    user_id: str = Field(..., description="User identifier")


class VoiceSessionStartResponse(BaseModel):
    session_id: str
    status: str
    message: str


class VoiceConversationTurn(BaseModel):
    """A single turn in the conversation."""
    id: str
    user_text: str
    assistant_text: str
    user_stress_score: Optional[float] = None
    assistant_stress_score: Optional[float] = None
    timestamp: str


class VoiceConversationHistory(BaseModel):
    """Conversation history for the current session."""
    session_id: str
    turns: list[VoiceConversationTurn] = []
    total_duration: float = 0.0