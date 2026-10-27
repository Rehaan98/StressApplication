"""
Voice Stress Analysis API Endpoints

POST /voice/analyze      → analyze voice audio for stress
POST /voice/start        → start a conversation session
POST /voice/turn         → process a conversation turn
GET  /voice/session      → get current session status
"""

import time
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.core.database import get_db
from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.schemas.voice import (
    VoiceAnalyzeRequest,
    VoiceAnalyzeResponse,
    VoiceSessionStartRequest,
    VoiceSessionStartResponse,
    VoiceConversationHistory,
)
from backend.app.services.voice_service import (
    analyze_voice_stress,
    detect_voice_activity,
    get_conversation_manager,
    reset_conversation_session,
)
from backend.app.models.user import User

router = APIRouter()


@router.post("/analyze", response_model=VoiceAnalyzeResponse)
async def voice_analyze(
    req: VoiceAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = analyze_voice_stress(
            audio_base64=req.audio_base64,
            sample_rate=req.sample_rate,
            transcript=getattr(req, "transcript", None),
        )

        features = result.get("voice_features", result.get("features", {}))
        # Ensure JSON-serializable floats
        safe_features = {}
        try:
            for k, v in (features or {}).items():
                safe_features[str(k)] = float(v)
        except Exception:
            safe_features = {}

        session_id = getattr(req, "session_id", None) or str(uuid.uuid4())

        safe_interventions = []
        for iv in result.get("interventions", []) or []:
            try:
                safe_interventions.append(
                    {
                        "id": str(iv.get("id", "")),
                        "category": str(iv.get("category", "")),
                        "title": str(iv.get("title", "")),
                        "summary": str(iv.get("summary", "")),
                        "protocol": [str(s) for s in (iv.get("protocol", []) or [])][:6],
                        "evidence_base": str(iv.get("evidence_base", "")),
                        "difficulty": str(iv.get("difficulty", "")),
                        "duration_min": int(iv.get("duration_min", 0) or 0),
                        "relevance_score": float(iv.get("relevance_score", 0) or 0),
                    }
                )
            except Exception:
                continue

        def _opt_score(key: str):
            v = result.get(key, None)
            try:
                return None if v is None else max(0.0, min(1.0, float(v)))
            except Exception:
                return None

        def _opt_conf(key: str):
            v = result.get(key, None)
            try:
                return None if v is None else max(0.0, min(1.0, float(v)))
            except Exception:
                return None

        return VoiceAnalyzeResponse(
            stress_score=float(result["stress_score"]),
            confidence=float(result["confidence"]),
            stress_level=str(result["stress_level"]),
            voice_features=safe_features,
            session_id=session_id,
            voice_score=_opt_score("voice_score"),
            text_score=_opt_score("text_score"),
            voice_confidence=_opt_conf("voice_confidence"),
            text_confidence=_opt_conf("text_confidence"),
            transcript=(result.get("transcript") if isinstance(result.get("transcript"), str) else (getattr(req, "transcript", None) or None)),
            text_keywords=[str(k) for k in (result.get("text_keywords", []) or [])][:8],
            emotion_hint=str(result.get("emotion_hint") or "") or None,
            explanation=str(result.get("explanation") or "") or None,
            interventions=safe_interventions,
            insufficient_evidence=bool(result.get("insufficient_evidence", False)),
            voice_available=bool(result.get("voice_available", True)),
            audio_level=result.get("audio_level"),
            quiet_warning=result.get("quiet_warning"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Voice analysis failed: {str(e)}",
        )


@router.post("/start", response_model=VoiceSessionStartResponse)
async def voice_start_session(
    req: VoiceSessionStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        reset_conversation_session(req.session_id)

        manager = get_conversation_manager(req.session_id)

        first_question = manager.get_next_question()

        return VoiceSessionStartResponse(
            session_id=req.session_id,
            status="started",
            message=first_question or "Welcome to your stress assessment.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start voice session: {str(e)}",
        )


@router.post("/turn", response_model=VoiceConversationHistory)
async def voice_process_turn(
    session_id: str,
    user_text: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        manager = get_conversation_manager(session_id)

        if not manager.should_continue():
            summary = manager.get_session_summary()
            reset_conversation_session(session_id)
            return VoiceConversationHistory(
                session_id=session_id,
                turns=summary.get("turns", []),
                total_duration=summary.get("duration_seconds", 0),
            )

        question = manager.get_next_question(user_text)

        turn_record = {
            "id": f"turn_{manager.turn_count}",
            "user_text": user_text or "",
            "assistant_text": question or "",
            "timestamp": time.time(),
        }

        manager.record_turn(turn_record)

        response_text = question or "Thank you for sharing that."

        return VoiceConversationHistory(
            session_id=session_id,
            turns=[turn_record],
            total_duration=0.0,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process conversation turn: {str(e)}",
        )


@router.get("/session/{session_id}", response_model=VoiceConversationHistory)
async def voice_get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        manager = get_conversation_manager(session_id)

        summary = manager.get_session_summary()

        return VoiceConversationHistory(
            session_id=session_id,
            turns=summary.get("turns", []),
            total_duration=summary.get("duration_seconds", 0.0),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session status: {str(e)}",
        )
