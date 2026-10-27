"""
Synchronized multimodal assessment sessions.

One session coordinates voice + facial + questionnaire evidence arriving at
different times: each modality result is timestamped, quality-flagged, and
fused on demand (live provisional) or persisted on finalize. State machine:

  idle → initializing → collecting → analyzing → finalizing → completed
                                        ↘ error (recoverable → collecting)
  any → cancelled (DELETE)

Sessions live in memory with idle TTL (like conversation sessions); only the
FINALIZED result is persisted (MultimodalAssessment row, no raw audio/frames).
Stale slots (older than SYNC_WINDOW_S) are still fused but flagged, never
silently mixed with fresh evidence.
"""

import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from backend.app.services import multimodal as mm

SYNC_WINDOW_S = float(os.getenv("MULTIMODAL_SYNC_WINDOW_S", "900") or 900.0)
SESSION_TTL_S = float(os.getenv("MULTIMODAL_SESSION_TTL_MIN", "30") or 30.0) * 60.0

VALID_TRANSITIONS = {
    "idle": ("initializing", "cancelled"),
    "initializing": ("collecting", "error", "cancelled"),
    "collecting": ("analyzing", "finalizing", "error", "cancelled"),
    "analyzing": ("collecting", "finalizing", "error", "cancelled"),
    "finalizing": ("completed", "error", "cancelled"),
    "error": ("collecting", "cancelled"),
    "completed": (),
    "cancelled": (),
}


@dataclass
class ModalitySlot:
    available: bool = False
    score: Optional[float] = None
    confidence: float = 0.0
    level: str = "Unknown"
    detail: Dict[str, Any] = field(default_factory=dict)
    updated_at: Optional[float] = None
    model_version: str = ""
    stale: bool = False


@dataclass
class AssessmentSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    status: str = "idle"
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    assessment_id: Optional[str] = None
    voice_transcript: str = ""
    slots: Dict[str, ModalitySlot] = field(default_factory=dict)
    error: Optional[str] = None
    finalized_id: Optional[str] = None

    def touch(self) -> None:
        self.last_active = time.time()

    def transition(self, nxt: str) -> None:
        allowed = VALID_TRANSITIONS.get(self.status, ())
        if nxt not in allowed:
            raise ValueError(f"Cannot move session from {self.status} to {nxt}.")
        self.status = nxt
        self.touch()
        if nxt != "error":
            self.error = None


_sessions: Dict[str, AssessmentSession] = {}


def _prune() -> None:
    now = time.time()
    for sid in [s for s, x in _sessions.items() if now - x.last_active > SESSION_TTL_S]:
        _sessions.pop(sid, None)


def create_session(user_id: str) -> AssessmentSession:
    _prune()
    sess = AssessmentSession(user_id=user_id,
                             slots={k: ModalitySlot() for k in ("questionnaire", "voice", "facial")})
    sess.transition("initializing")
    sess.transition("collecting")
    _sessions[sess.session_id] = sess
    return sess


def fetch_session(session_id: str, user_id: str) -> AssessmentSession:
    from fastapi import HTTPException, status

    sess = _sessions.get(session_id)
    if sess is None or sess.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Assessment session not found.")
    if time.time() - sess.last_active > SESSION_TTL_S:
        _sessions.pop(session_id, None)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Assessment session expired.")
    if sess.status in ("completed", "cancelled"):
        raise HTTPException(status_code=status.HTTP_410_GONE,
                            detail=f"Assessment session already {sess.status}.")
    return sess


def drop_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


def _slot_to_modality(name: str, slot: ModalitySlot) -> mm.ModalityResult:
    now = time.time()
    stale = bool(slot.updated_at is not None and (now - slot.updated_at) > SYNC_WINDOW_S)
    slot.stale = stale
    return mm.ModalityResult(name=name, score=slot.score if slot.available else None,
                             confidence=slot.confidence, available=slot.available,
                             level=slot.level,
                             detail={**slot.detail, "stale": stale,
                                     "age_seconds": round(now - slot.updated_at, 1)
                                     if slot.updated_at else None,
                                     "model_version": slot.model_version})


def live_view(sess: AssessmentSession) -> Dict[str, Any]:
    """Provisional fusion over current slots (persist=False)."""
    modalities = [_slot_to_modality(k, s) for k, s in sess.slots.items()]
    fused = mm.fuse_modalities(modalities)
    factors = mm.build_factors(modalities)
    limitations = mm.build_limitations(modalities, fused.get("single", False))
    if any(s.stale for s in sess.slots.values() if s.available):
        limitations.insert(0, "Some inputs are older than "
                           f"{int(SYNC_WINDOW_S // 60)} minutes — treat the mix cautiously.")
    if fused.get("insufficient"):
        limitations.insert(0, "Not enough evidence yet — add a questionnaire, voice, or face input.")
    return {
        "session_id": sess.session_id,
        "assessment_status": "provisional",
        "overall_estimate": fused["score"],
        "overall_category": fused["level"],
        "uncertainty": round(1.0 - fused["confidence"], 3),
        "fusion_method": mm.FUSION_METHOD,
        "available_modalities": [m.name for m in modalities if m.available],
        "missing_modalities": [m.name for m in modalities if not m.available],
        "voice_result": _public_slot("voice", sess),
        "face_result": _public_slot("facial", sess),
        "questionnaire_result": _public_slot("questionnaire", sess),
        "contributing_factors": factors,
        "model_versions": {k: (s.model_version or "n/a") for k, s in sess.slots.items()},
        "updated_at": max([s.updated_at or 0 for s in sess.slots.values()] + [sess.created_at]),
        "limitations": limitations,
    }


def _public_slot(name: str, sess: AssessmentSession) -> Optional[Dict[str, Any]]:
    s = sess.slots[name]
    if not s.available:
        return None
    return {"score": s.score, "confidence": s.confidence, "level": s.level,
            "detail": s.detail, "updated_at": s.updated_at, "stale": s.stale,
            "model_version": s.model_version}


def session_state(sess: AssessmentSession) -> Dict[str, Any]:
    return {
        "session_id": sess.session_id,
        "assessment_status": sess.status,
        "created_at": sess.created_at,
        "voice_status": _mod_status(sess, "voice"),
        "facial_status": _mod_status(sess, "facial"),
        "questionnaire_status": _mod_status(sess, "questionnaire"),
        "error": sess.error,
        "finalized_id": sess.finalized_id,
    }


def _mod_status(sess: AssessmentSession, name: str) -> Dict[str, Any]:
    s = sess.slots[name]
    return {"available": s.available, "updated_at": s.updated_at,
            "quality": s.detail.get("quality", "unknown"),
            "error": s.detail.get("error")}


async def record_questionnaire(db, sess: AssessmentSession, assessment_id: str) -> Dict[str, Any]:
    from sqlalchemy.future import select
    from sqlalchemy import desc
    from backend.app.models.assessment import StressAssessment
    from backend.app.models.prediction import Prediction
    from backend.app.models.explainability_log import ExplainabilityLog

    stmt = select(StressAssessment).where(StressAssessment.id == assessment_id)
    res = await db.execute(stmt)
    assessment = res.scalars().first()
    if assessment is None or assessment.user_id != sess.user_id:
        raise ValueError("Questionnaire assessment not found.")
    pred, drivers = None, []
    try:
        p = await db.execute(select(Prediction)
                             .where(Prediction.assessment_id == assessment.id,
                                    Prediction.user_id == sess.user_id)
                             .order_by(desc(Prediction.created_at)).limit(1))
        pred = p.scalars().first()
        if pred is not None:
            x = await db.execute(select(ExplainabilityLog)
                                 .where(ExplainabilityLog.prediction_id == pred.id))
            log = x.scalars().first()
            if log and log.shap_top_drivers:
                drivers = list(log.shap_top_drivers)[:5]
    except Exception:
        pass
    m = mm.score_questionnaire(assessment, pred, drivers)
    _store(sess, "questionnaire", m, quality="complete", model_version="pss10-official")
    sess.assessment_id = assessment.id
    return _public_slot("questionnaire", sess) or {}


async def record_voice(sess: AssessmentSession, audio_base64: Optional[str],
                       transcript: Optional[str]) -> Dict[str, Any]:
    if transcript:
        sess.voice_transcript = transcript.strip()[:2000]
    m = mm.score_voice(audio_base64, transcript)
    if not m.available:
        sess.slots["voice"] = ModalitySlot(
            available=False, detail={"note": m.detail.get("note", "Voice unavailable."),
                                     "error": m.detail.get("note", ""), "quality": "failed"},
            updated_at=time.time(), model_version="voice-heuristic-v1")
    else:
        _store(sess, "voice", m,
               quality=str(m.detail.get("audio_level") or "unknown"),
               model_version="voice-heuristic-v1")
    sess.touch()
    return _public_slot("voice", sess) or {}


async def record_facial(db, sess: AssessmentSession, image_base64: Optional[str],
                        reading_id: Optional[str]) -> Dict[str, Any]:
    m = await mm.score_facial(db, sess.user_id, image_base64, reading_id)
    if not m.available:
        sess.slots["facial"] = ModalitySlot(
            available=False, detail={"note": m.detail.get("note", "Facial unavailable."),
                                     "error": m.detail.get("note", ""), "quality": "failed"},
            updated_at=time.time(), model_version=m.detail.get("model", "ferplus-fer2013"))
    else:
        _store(sess, "facial", m, quality="ok" if m.detail.get("fresh_capture", True) else "stored",
               model_version=str(m.detail.get("model", "ferplus-fer2013")))
    sess.touch()
    return _public_slot("facial", sess) or {}


def _store(sess: AssessmentSession, name: str, m: mm.ModalityResult,
           quality: str, model_version: str) -> None:
    sess.slots[name] = ModalitySlot(
        available=True, score=m.score, confidence=m.confidence, level=m.level,
        detail={**m.detail, "quality": quality}, updated_at=time.time(),
        model_version=model_version)
    sess.touch()


async def finalize_session(db, sess: AssessmentSession) -> Dict[str, Any]:
    modalities = [_slot_to_modality(k, s) for k, s in sess.slots.items()]
    fused = mm.fuse_modalities(modalities)
    if fused.get("insufficient"):
        raise ValueError("No usable evidence in any modality — add at least one input.")
    sess.transition("finalizing")
    try:
        res = await mm.finalize_modalities(
            db, sess.user_id, modalities, fused,
            assessment_id=sess.assessment_id,
            facial_reading_id=(sess.slots["facial"].detail.get("reading_id")
                               if sess.slots["facial"].available else None),
            voice_transcript=sess.voice_transcript or None,
            persist=True)
    except Exception as e:
        sess.transition("error")
        sess.error = str(e)[:300]
        raise
    sess.finalized_id = res.get("id")
    sess.transition("completed")
    # Keep the completed record readable via history; drop live session memory.
    drop_session(sess.session_id)
    res["assessment_status"] = "final"
    return res
