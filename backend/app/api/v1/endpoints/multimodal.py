"""
Unified multimodal assessment endpoints (additive — existing routes untouched).

POST /multimodal/assess  → run questionnaire + voice + facial → one fused result
GET  /multimodal/        → user's unified assessment history
GET  /multimodal/{id}    → one stored unified assessment
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.models.user import User
from backend.app.schemas.multimodal import (
    MultimodalAssessRequest,
    MultimodalAssessResponse,
    MultimodalHistoryItem,
)
from backend.app.services.multimodal import MultimodalService

router = APIRouter()


@router.post("/assess", response_model=MultimodalAssessResponse)
async def run_unified_assessment(
    req: MultimodalAssessRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not any([req.assessment_id, req.voice_audio_base64,
                (req.voice_transcript or "").strip(),
                req.facial_image, req.facial_reading_id]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one input: questionnaire assessment, voice, or facial.",
        )
    try:
        res = await MultimodalService.assess(
            db, current_user.id,
            assessment_id=req.assessment_id,
            voice_audio_base64=req.voice_audio_base64,
            voice_transcript=req.voice_transcript,
            facial_image=req.facial_image,
            facial_reading_id=req.facial_reading_id,
        )
        return MultimodalAssessResponse(**res)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unified assessment failed: {e}",
        )


@router.get("/", response_model=List[MultimodalHistoryItem])
async def list_unified_assessments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
):
    return await MultimodalService.history(db, current_user.id, limit)


@router.get("/{record_id}", response_model=MultimodalAssessResponse)
async def get_unified_assessment(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = await MultimodalService.get_by_id(db, record_id, current_user.id)
    mods = row.modality_results or {}

    def _mod(name: str):
        m = mods.get(name) or {}
        if not m.get("available"):
            return None
        return {"score": m.get("score"), "confidence": m.get("confidence", 0),
                "level": m.get("level", "Unknown"), "detail": m.get("detail", {})}

    return MultimodalAssessResponse(
        id=row.id, assessment_id=row.id, assessment_timestamp=row.created_at,
        overall_estimate=row.overall_score, overall_category=row.overall_category,
        uncertainty=round(1.0 - (row.confidence or 0), 3),
        fusion_method=row.fusion_method,
        available_modalities=row.available_modalities or [],
        missing_modalities=row.missing_modalities or [],
        voice_result=_mod("voice"), face_result=_mod("facial"),
        questionnaire_result=_mod("questionnaire"),
        contributing_factors=row.contributing_factors or [],
        recommendations=[],
        limitations=row.limitations or [],
        overall_note="",
    )
