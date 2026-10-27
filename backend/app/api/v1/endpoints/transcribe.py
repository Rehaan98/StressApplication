"""
Voice transcription endpoints (server-side STT fallback).

POST /voice/transcribe        → multipart audio upload → transcript
GET  /voice/transcribe/status → whether a provider is configured

Audio is transcribed in memory and never stored. All routes require auth,
like the rest of the voice API.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.transcribe import TranscribeResponse, TranscribeStatusResponse
from backend.app.services.transcription import (
    EmptyRecording,
    MalformedAudio,
    ProviderFailed,
    ProviderNotConfigured,
    provider_status,
    transcribe_upload,
)

router = APIRouter()


@router.get("/transcribe/status", response_model=TranscribeStatusResponse)
async def transcribe_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # No secrets in the response — only whether transcription can work.
    info = provider_status()
    return TranscribeStatusResponse(
        provider=str(info.get("provider", "none")),
        configured=bool(info.get("configured", False)),
        max_mb=float(info.get("max_mb", 10.0)),
        note=str(info.get("note", "")),
    )


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    audio: UploadFile = File(..., description="Recorded speech (webm/mp4/wav/ogg, ≤10MB)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await transcribe_upload(audio)
        return TranscribeResponse(
            transcript=result.transcript,
            provider=result.provider,
            duration_seconds=result.duration_seconds,
            language=result.language,
            warning=result.warning,
        )
    except ProviderNotConfigured as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except EmptyRecording as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except MalformedAudio as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ProviderFailed as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY if e.retryable
            else status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
