"""
Multimodal assessment schemas — additive, existing contracts untouched.
Null (not zero) marks missing modalities.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class MultimodalAssessRequest(BaseModel):
    assessment_id: Optional[str] = Field(default=None, description="Completed questionnaire assessment")
    voice_audio_base64: Optional[str] = Field(default=None, description="Recorded speech (WAV preferred)")
    voice_transcript: Optional[str] = Field(default=None, description="Typed or transcribed words")
    facial_image: Optional[str] = Field(default=None, description="Base64 JPEG frame (raw, no data-URI prefix)")
    facial_reading_id: Optional[str] = Field(default=None, description="Existing facial analysis id")


class ModalityPayload(BaseModel):
    score: Optional[float] = None
    confidence: float = 0.0
    level: str = "Unknown"
    detail: Dict[str, Any] = {}


class MultimodalAssessResponse(BaseModel):
    id: str
    assessment_id: str
    assessment_timestamp: datetime
    overall_estimate: Optional[float] = None
    overall_category: str = "Uncertain"
    uncertainty: float = 1.0
    fusion_method: str = ""
    available_modalities: List[str] = []
    missing_modalities: List[str] = []
    voice_result: Optional[ModalityPayload] = None
    face_result: Optional[ModalityPayload] = None
    questionnaire_result: Optional[ModalityPayload] = None
    contributing_factors: List[Dict[str, Any]] = []
    recommendations: List[Dict[str, Any]] = []
    limitations: List[str] = []
    overall_note: str = ""


class MultimodalHistoryItem(BaseModel):
    id: str
    overall_category: str
    overall_score: float
    confidence: float
    available_modalities: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True


class SessionCreateResponse(BaseModel):
    session_id: str
    assessment_status: str = "collecting"
    created_at: float = 0.0


class SessionVoiceRequest(BaseModel):
    audio_base64: Optional[str] = Field(default=None)
    transcript: Optional[str] = Field(default=None, max_length=2000)


class SessionFaceRequest(BaseModel):
    image_base64: Optional[str] = Field(default=None)
    reading_id: Optional[str] = Field(default=None)


class SessionQuestionnaireRequest(BaseModel):
    assessment_id: str


class SessionModalityStatus(BaseModel):
    available: bool = False
    updated_at: Optional[float] = None
    quality: str = "unknown"
    error: Optional[str] = None


class SessionStateResponse(BaseModel):
    session_id: str
    assessment_status: str = "collecting"
    created_at: float = 0.0
    voice_status: SessionModalityStatus = SessionModalityStatus()
    facial_status: SessionModalityStatus = SessionModalityStatus()
    questionnaire_status: SessionModalityStatus = SessionModalityStatus()
    error: Optional[str] = None
    finalized_id: Optional[str] = None


class SessionLiveResponse(BaseModel):
    session_id: str
    assessment_status: str = "provisional"
    overall_estimate: Optional[float] = None
    overall_category: str = "Uncertain"
    uncertainty: float = 1.0
    fusion_method: str = ""
    available_modalities: List[str] = []
    missing_modalities: List[str] = []
    voice_result: Optional[Dict[str, Any]] = None
    face_result: Optional[Dict[str, Any]] = None
    questionnaire_result: Optional[Dict[str, Any]] = None
    contributing_factors: List[Dict[str, Any]] = []
    model_versions: Dict[str, str] = {}
    updated_at: float = 0.0
    limitations: List[str] = []
