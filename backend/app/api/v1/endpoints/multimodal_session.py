"""
Synchronized assessment-session endpoints (additive).

POST   /multimodal/sessions                  → create session (collecting)
GET    /multimodal/sessions/{id}             → session state + modality status
POST   /multimodal/sessions/{id}/voice       → score voice, store slot
POST   /multimodal/sessions/{id}/face        → score facial, store slot
POST   /multimodal/sessions/{id}/questionnaire → score questionnaire, store slot
GET    /multimodal/sessions/{id}/live        → provisional fused view (no persist)
POST   /multimodal/sessions/{id}/finalize    → final fused + persisted result
DELETE /multimodal/sessions/{id}             → cancel (drop live memory)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.models.user import User
from backend.app.schemas.multimodal import (
    MultimodalAssessResponse,
    SessionCreateResponse,
    SessionFaceRequest,
    SessionLiveResponse,
    SessionQuestionnaireRequest,
    SessionStateResponse,
    SessionVoiceRequest,
)
from backend.app.services import multimodal_session as ms

router = APIRouter()


@router.post("/sessions", response_model=SessionCreateResponse)
async def create_session(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sess = ms.create_session(current_user.id)
    return SessionCreateResponse(session_id=sess.session_id,
                                 assessment_status=sess.status,
                                 created_at=sess.created_at)


@router.get("/sessions/{session_id}", response_model=SessionStateResponse)
async def get_session_state(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sess = ms.fetch_session(session_id, current_user.id)
    return SessionStateResponse(**ms.session_state(sess))


@router.post("/sessions/{session_id}/voice")
async def submit_voice(
    session_id: str,
    req: SessionVoiceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sess = ms.fetch_session(session_id, current_user.id)
    if not req.audio_base64 and not (req.transcript or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Provide voice audio or transcript.")
    _analyze(sess)
    try:
        out = await ms.record_voice(sess, req.audio_base64, req.transcript)
        return {"session_id": session_id, "voice_result": out,
                "voice_status": ms.session_state(sess)["voice_status"]}
    except ValueError as e:
        _collect(sess)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    finally:
        _collect(sess)


@router.post("/sessions/{session_id}/face")
async def submit_face(
    session_id: str,
    req: SessionFaceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sess = ms.fetch_session(session_id, current_user.id)
    if not req.image_base64 and not req.reading_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Provide a facial image or reading id.")
    _analyze(sess)
    try:
        out = await ms.record_facial(db, sess, req.image_base64, req.reading_id)
        return {"session_id": session_id, "face_result": out,
                "facial_status": ms.session_state(sess)["facial_status"]}
    finally:
        _collect(sess)


@router.post("/sessions/{session_id}/questionnaire")
async def submit_questionnaire(
    session_id: str,
    req: SessionQuestionnaireRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sess = ms.fetch_session(session_id, current_user.id)
    _analyze(sess)
    try:
        out = await ms.record_questionnaire(db, sess, req.assessment_id)
        return {"session_id": session_id, "questionnaire_result": out,
                "questionnaire_status": ms.session_state(sess)["questionnaire_status"]}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    finally:
        _collect(sess)


@router.get("/sessions/{session_id}/live", response_model=SessionLiveResponse)
async def get_live(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sess = ms.fetch_session(session_id, current_user.id)
    return SessionLiveResponse(**ms.live_view(sess))


@router.post("/sessions/{session_id}/finalize", response_model=MultimodalAssessResponse)
async def finalize(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sess = ms.fetch_session(session_id, current_user.id)
    try:
        res = await ms.finalize_session(db, sess)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    res.pop("assessment_status", None)  # internal marker; not part of the contract
    return MultimodalAssessResponse(**res)


@router.delete("/sessions/{session_id}")
async def cancel_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sess = ms.fetch_session(session_id, current_user.id)
    try:
        sess.transition("cancelled")
    except ValueError:
        pass
    ms.drop_session(session_id)
    return {"session_id": session_id, "assessment_status": "cancelled"}


def _analyze(sess) -> None:
    try:
        sess.transition("analyzing")
    except ValueError:
        pass


def _collect(sess) -> None:
    try:
        if sess.status == "analyzing":
            sess.transition("collecting")
    except ValueError:
        pass
