"""
Voice transcription schemas (server-side STT fallback).
"""

from typing import Optional
from pydantic import BaseModel, Field


class TranscribeResponse(BaseModel):
    transcript: str = Field(..., description="Recognized text (may be empty with a warning)")
    provider: str = Field(..., description="Transcription provider used")
    duration_seconds: float = Field(default=0.0)
    language: Optional[str] = Field(default=None)
    warning: Optional[str] = Field(default=None, description="Present when no speech was recognized")


class TranscribeStatusResponse(BaseModel):
    provider: str = "none"
    configured: bool = False
    max_mb: float = 10.0
    note: str = ""
