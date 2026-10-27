"""
Unified multimodal stress assessment service.

Runs the three EXISTING pipelines independently — questionnaire (PSS-10
official scoring + the trained tabular ML model as corroboration), voice
(acoustic + language fusion), facial (FER+ CNN) — normalizes each to 0-1,
and combines the available evidence with confidence-aware weighting.

Honesty rules (no exceptions):
  * Missing modalities are marked unavailable — never zero, never neutral.
  * Heuristic confidences are uncalibrated: fusion is labeled provisional /
    experimental and is never presented as a clinical diagnosis.
  * The questionnaire recalls the past month while voice/face capture the
    moment — different constructs, preserved as distinct interpretations.
  * Voice's internal acoustic+text fusion counts as ONE modality (no double
    counting); the ML prediction corroborates the questionnaire, not a vote.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc

from backend.app.models.assessment import StressAssessment
from backend.app.models.prediction import Prediction
from backend.app.models.explainability_log import ExplainabilityLog
from backend.app.models.facial_analysis import FacialAnalysis
from backend.app.models.multimodal import MultimodalAssessment

FUSION_METHOD = "confidence-weighted-provisional-v1"
FUSION_VERSION = "1.0"

NON_DIAGNOSTIC_NOTE = (
    "This is an AI-generated estimate to support self-awareness, not a medical "
    "diagnosis. If you're struggling, consider talking to someone you trust or a professional."
)

# Standard PSS-10 item wordings (labels only — scoring is untouched).
PSS_ITEMS = {
    1: "upset by something unexpected",
    2: "unable to control important things",
    3: "nervous or stressed",
    4: "confident handling problems (reversed)",
    5: "things going your way (reversed)",
    6: "could not cope",
    7: "able to control irritations (reversed)",
    8: "on top of things (reversed)",
    9: "angered by things outside control",
    10: "difficulties piling up",
}
REVERSED_ITEMS = {4, 5, 7, 8}


def _band(score: float) -> str:
    if score < 0.33:
        return "Low"
    if score < 0.60:
        return "Moderate"
    if score < 0.80:
        return "High"
    return "Severe"


@dataclass
class ModalityResult:
    name: str
    score: Optional[float]  # 0-1, None when unavailable
    confidence: float
    available: bool
    level: str = "Unknown"
    detail: Dict[str, Any] = field(default_factory=dict)


def score_questionnaire(assessment: StressAssessment,
                        ml_prediction: Optional[Prediction] = None,
                        shap_drivers: Optional[List[Dict[str, Any]]] = None) -> ModalityResult:
    """PSS-10 official scoring (reverse 4,5,7,8 — same as StressService)."""
    raw = {i: int(getattr(assessment, f"pss_q{i}") or 0) for i in range(1, 11)}
    scored = {i: (4 - v if i in REVERSED_ITEMS else v) for i, v in raw.items()}
    total = sum(scored.values())
    total = max(0, min(40, total))
    norm = round(total / 40.0, 4)
    # Official PSS-10 interpretation bands.
    level = "Low" if total <= 13 else ("Moderate" if total <= 26 else "High")
    top = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)[:3]
    factors = [
        {"source": "questionnaire",
         "text": f"Q{i} ({PSS_ITEMS[i]}): scored {s}/4",
         "contribution": round(s / 4.0, 3)}
        for i, s in top if s >= 2
    ]
    detail: Dict[str, Any] = {
        "raw_score": total, "score_range": [0, 40],
        "interpretation": f"PSS-10 total {total}/40 → {level} perceived stress (past month)",
        "instrument": "PSS-10 (validated); unanswered items default to neutral per app convention",
        "top_items": factors,
    }
    if ml_prediction is not None:
        detail["ml_corroroboration"] = {
            "level": ml_prediction.stress_level,
            "confidence": float(ml_prediction.confidence_score or 0),
            "agrees": ml_prediction.stress_level in (level, _band(norm)),
        }
        for d in (shap_drivers or [])[:3]:
            try:
                factors.append({
                    "source": "ml-model",
                    "text": f"{d.get('feature')}: SHAP {float(d.get('shap_value', 0)):+.3f}",
                    "contribution": abs(float(d.get('shap_value', 0))),
                })
            except (TypeError, ValueError):
                continue
    return ModalityResult(name="questionnaire", score=norm, confidence=0.85,
                          available=True, level=level, detail=detail)


def score_voice(audio_base64: Optional[str] = None,
                transcript: Optional[str] = None) -> ModalityResult:
    """Voice via the existing pipeline. Unavailable — never faked — on failure."""
    from backend.app.services import voice_service as vs

    if not (audio_base64 or (transcript or "").strip()):
        return ModalityResult(name="voice", score=None, confidence=0.1,
                              available=False, detail={"note": "No voice input provided."})
    try:
        if audio_base64:
            r = vs.analyze_voice_stress(audio_base64, 16000, transcript=transcript)
        else:
            t = vs.analyze_text_stress(transcript)
            r = {"stress_score": t["text_score"], "confidence": t["confidence"],
                 "stress_level": t["text_level"], "voice_available": False,
                 "audio_level": None, "quiet_warning": None,
                 "text_keywords": t.get("keywords", []),
                 "emotion_hint": t.get("emotion_hint", ""),
                 "explanation": "Words-only reading (no audio).",
                 "insufficient_evidence": False}
    except ValueError as e:
        return ModalityResult(name="voice", score=None, confidence=0.15,
                              available=False, detail={"note": f"Voice analysis failed: {e}"})
    except Exception as e:
        return ModalityResult(name="voice", score=None, confidence=0.15,
                              available=False, detail={"note": f"Voice model error: {type(e).__name__}"})
    if r.get("insufficient_evidence"):
        return ModalityResult(name="voice", score=None, confidence=0.15,
                              available=False,
                              detail={"note": r.get("explanation", "Insufficient voice evidence.")})
    return ModalityResult(
        name="voice", score=round(float(r["stress_score"]), 4),
        confidence=round(float(r.get("confidence", 0.5)), 4), available=True,
        level=str(r.get("stress_level", "Moderate")),
        detail={"acoustic_available": bool(r.get("voice_available", True)),
                "audio_level": r.get("audio_level"),
                "emotion_hint": r.get("emotion_hint", ""),
                "keywords": list(r.get("text_keywords", []) or [])[:6],
                "explanation": r.get("explanation", ""),
                "quiet_warning": r.get("quiet_warning")},
    )


async def score_facial(db: AsyncSession, user_id: str,
                       image_base64: Optional[str] = None,
                       reading_id: Optional[str] = None) -> ModalityResult:
    """Facial via the existing CNN (fresh frame) or a stored reading."""
    from backend.app.services.facial_service import FacialService

    if image_base64:
        try:
            r = await FacialService.analyze(db, user_id, image_base64, source="webcam")
        except Exception as e:
            msg = getattr(e, "detail", None) or f"{type(e).__name__}"
            return ModalityResult(name="facial", score=None, confidence=0.15,
                                  available=False, detail={"note": f"Facial analysis failed: {msg}"})
        return ModalityResult(
            name="facial", score=round(float(r["stress_score"]) / 100.0, 4),
            confidence=round(float(r.get("confidence_score", 0.5)), 4), available=True,
            level=str(r.get("stress_level", "Moderate")),
            detail={"reading_id": r.get("id"), "emotion": r.get("dominant_emotion", ""),
                    "emotion_probabilities": r.get("emotion_probabilities", {}),
                    "model": r.get("model", "unknown"),
                    "fresh_capture": True},
        )
    if reading_id:
        stmt = select(FacialAnalysis).where(FacialAnalysis.id == reading_id)
        res = await db.execute(stmt)
        row = res.scalars().first()
        if row is None or row.user_id != user_id:
            return ModalityResult(name="facial", score=None, confidence=0.1,
                                  available=False, detail={"note": "Facial reading not found."})
        return ModalityResult(
            name="facial", score=round(float(row.stress_score) / 100.0, 4),
            confidence=round(float(row.confidence_score or 0.5), 4), available=True,
            level=str(row.stress_level),
            detail={"reading_id": row.id, "emotion": row.dominant_emotion,
                    "emotion_probabilities": row.emotion_probabilities or {},
                    "model": row.model, "fresh_capture": False},
        )
    return ModalityResult(name="facial", score=None, confidence=0.1,
                          available=False, detail={"note": "No facial input provided."})


def fuse_modalities(modalities: List[ModalityResult]) -> Dict[str, Any]:
    """Confidence×decisiveness fusion over AVAILABLE modalities only."""
    usable = [m for m in modalities if m.available and m.score is not None]
    if not usable:
        return {"score": None, "level": "Uncertain", "confidence": 0.15,
                "weights": {}, "single": False, "insufficient": True}
    raw = {m.name: max(0.05, m.confidence) * (0.5 + abs(m.score - 0.5) * 2.0) for m in usable}
    total = sum(raw.values())
    weights = {k: round(v / total, 3) for k, v in raw.items()}
    if len(weights) > 1:  # clamp only meaningful with 2+ modalities
        for k in list(weights):
            if weights[k] > 0.70:
                excess = weights[k] - 0.70
                weights[k] = 0.70
                others = [o for o in weights if o != k]
                if others:
                    share = excess / len(others)
                    for o in others:
                        weights[o] = round(weights[o] + share, 3)
    by_name = {m.name: m for m in usable}
    final = round(sum(by_name[k].score * weights[k] for k in weights), 4)  # type: ignore[arg-type]
    conf = round(max(0.15, min(0.95, sum(by_name[k].confidence * weights[k] for k in weights))), 3)
    return {"score": final, "level": _band(final), "confidence": conf,
            "weights": weights, "single": len(usable) == 1, "insufficient": False}


def build_factors(modalities: List[ModalityResult]) -> List[Dict[str, Any]]:
    factors: List[Dict[str, Any]] = []
    for m in modalities:
        if not m.available:
            continue
        if m.name == "questionnaire":
            factors.extend(m.detail.get("top_items", []))
        elif m.name == "voice":
            for kw in (m.detail.get("keywords", []) or [])[:3]:
                factors.append({"source": "voice", "text": f"Spoke about: {kw}", "contribution": 0.5})
            if m.detail.get("emotion_hint"):
                factors.append({"source": "voice", "text": f"Voice emotion hint: {m.detail['emotion_hint']}",
                                "contribution": 0.5})
        elif m.name == "facial":
            emo = m.detail.get("emotion", "")
            if emo:
                factors.append({"source": "facial", "text": f"Facial expression read as: {emo}",
                                "contribution": round(float(m.score or 0), 3)})
    return factors[:8]


def build_limitations(modalities: List[ModalityResult], single: bool) -> List[str]:
    lim = [
        "Questionnaire recalls the past month; voice and facial capture this moment — related but distinct signals.",
        "Voice and facial confidences are heuristic, not calibrated probabilities.",
        "A smile doesn't prove calm, and a tense voice alone doesn't prove distress.",
        NON_DIAGNOSTIC_NOTE,
    ]
    if single:
        lim.insert(0, "Single-modality result: only one input contributed.")
    missing = [m.name for m in modalities if not m.available]
    if missing:
        lim.insert(0 if not single else 1,
                   f"Not included ({', '.join(missing)} unavailable) — never substituted with neutral scores.")
    return lim


def recommend_interventions(fused_level: str, transcript: str = "") -> List[Dict[str, Any]]:
    try:
        from backend.app.services.voice_service import _retrieve_voice_interventions

        return _retrieve_voice_interventions(fused_level, transcript or "", "", {}, top_k=3) or []
    except Exception:
        return []


async def finalize_modalities(db: AsyncSession, user_id: str,
                              modalities: List[ModalityResult],
                              fused: Dict[str, Any],
                              assessment_id: Optional[str] = None,
                              facial_reading_id: Optional[str] = None,
                              voice_transcript: Optional[str] = None,
                              persist: bool = True) -> Dict[str, Any]:
    """Fuse + explain + (optionally) persist. Shared by one-shot assess and sessions."""
    factors = build_factors(modalities)
    limitations = build_limitations(modalities, fused.get("single", False))
    available = [m.name for m in modalities if m.available]
    missing = [m.name for m in modalities if not m.available]

    if fused.get("insufficient"):
        overall_note = ("No usable input in any modality. Complete at least one of: "
                        "questionnaire, voice recording, or face scan.")
    elif fused.get("single"):
        overall_note = (f"Based on {available[0]} only — add other inputs for a fuller picture.")
    else:
        overall_note = (f"Combined from {', '.join(available)} using {FUSION_METHOD} "
                        f"(experimental, weights {fused['weights']}).")

    recommendations: List[Dict[str, Any]] = []
    if not fused.get("insufficient"):
        recommendations = recommend_interventions(fused["level"], voice_transcript or "")

    by_name = {m.name: m for m in modalities}
    record_id = None
    created_at = None
    if persist:
        if facial_reading_id is None and by_name.get("facial") is not None \
                and by_name["facial"].available:
            facial_reading_id = by_name["facial"].detail.get("reading_id")
        record = MultimodalAssessment(
            user_id=user_id,
            assessment_id=assessment_id,
            facial_reading_id=facial_reading_id,
            voice_transcript=(voice_transcript or "").strip() or None,
            overall_score=fused["score"] if fused["score"] is not None else 0.0,
            overall_category=fused["level"],
            confidence=fused["confidence"],
            fusion_method=FUSION_METHOD,
            fusion_version=FUSION_VERSION,
            available_modalities=available,
            missing_modalities=missing,
            modality_results={m.name: {"score": m.score, "confidence": m.confidence,
                                       "available": m.available, "level": m.level,
                                       "detail": m.detail} for m in modalities},
            contributing_factors=factors,
            limitations=limitations,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        record_id = record.id
        created_at = record.created_at

    def _mod(name: str) -> Optional[Dict[str, Any]]:
        m = by_name[name]
        if not m.available:
            return None
        return {"score": m.score, "confidence": m.confidence, "level": m.level,
                "detail": m.detail}

    from datetime import datetime, timezone

    return {
        "id": record_id,
        "assessment_id": record_id,
        "assessment_timestamp": created_at or datetime.now(timezone.utc),
        "overall_estimate": fused["score"],
        "overall_category": fused["level"],
        "uncertainty": round(1.0 - fused["confidence"], 3),
        "fusion_method": FUSION_METHOD,
        "available_modalities": available,
        "missing_modalities": missing,
        "voice_result": _mod("voice"),
        "face_result": _mod("facial"),
        "questionnaire_result": _mod("questionnaire"),
        "contributing_factors": factors,
        "recommendations": recommendations,
        "limitations": limitations,
        "overall_note": overall_note,
    }


class MultimodalService:
    @staticmethod
    async def assess(db: AsyncSession, user_id: str,
                     assessment_id: Optional[str] = None,
                     voice_audio_base64: Optional[str] = None,
                     voice_transcript: Optional[str] = None,
                     facial_image: Optional[str] = None,
                     facial_reading_id: Optional[str] = None) -> Dict[str, Any]:
        modalities: List[ModalityResult] = []

        # 1) Questionnaire (independent module, official scoring untouched).
        assessment = None
        if assessment_id:
            stmt = select(StressAssessment).where(StressAssessment.id == assessment_id)
            res = await db.execute(stmt)
            assessment = res.scalars().first()
            if assessment is None or assessment.user_id != user_id:
                assessment = None
        if assessment is not None:
            pred = None
            drivers: List[Dict[str, Any]] = []
            try:
                p_stmt = (select(Prediction)
                          .where(Prediction.assessment_id == assessment.id,
                                 Prediction.user_id == user_id)
                          .order_by(desc(Prediction.created_at)).limit(1))
                p_res = await db.execute(p_stmt)
                pred = p_res.scalars().first()
                if pred is not None:
                    x_stmt = select(ExplainabilityLog).where(ExplainabilityLog.prediction_id == pred.id)
                    x_res = await db.execute(x_stmt)
                    x_log = x_res.scalars().first()
                    if x_log and x_log.shap_top_drivers:
                        drivers = list(x_log.shap_top_drivers)[:5]
            except Exception:
                pred, drivers = None, []
            modalities.append(score_questionnaire(assessment, pred, drivers))
        else:
            modalities.append(ModalityResult(name="questionnaire", score=None, confidence=0.1,
                                             available=False,
                                             detail={"note": "No questionnaire assessment provided."}))

        # 2) Voice (independent module).
        modalities.append(score_voice(voice_audio_base64, voice_transcript))

        # 3) Facial (independent module).
        modalities.append(await score_facial(db, user_id, facial_image, facial_reading_id))

        fused = fuse_modalities(modalities)
        return await finalize_modalities(
            db, user_id, modalities, fused,
            assessment_id=assessment.id if assessment is not None else None,
            voice_transcript=voice_transcript,
        )

    @staticmethod
    async def history(db: AsyncSession, user_id: str, limit: int = 20) -> List[MultimodalAssessment]:
        stmt = (select(MultimodalAssessment).where(MultimodalAssessment.user_id == user_id)
                .order_by(desc(MultimodalAssessment.created_at)).limit(limit))
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, record_id: str, user_id: str) -> MultimodalAssessment:
        from fastapi import HTTPException, status

        stmt = select(MultimodalAssessment).where(MultimodalAssessment.id == record_id)
        res = await db.execute(stmt)
        row = res.scalars().first()
        if row is None or row.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Multimodal assessment not found.")
        return row
