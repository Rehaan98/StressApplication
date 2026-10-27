"""
Modular stress-inference engine (spec section 4).

Wraps the EXISTING validated pipelines — text (voice_language), acoustic
(voice_service), visual (facial pipeline outputs) — without changing them.
Each modality reports its own score, confidence, and availability; fusion is
confidence-aware; uncertainty is stated honestly in non-diagnostic language.

Nothing here claims a clinically validated percentage: user-facing wording
uses "possible elevated stress" / "you may be feeling overwhelmed", and the
module always notes it supports self-awareness rather than diagnosis.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


DISCLAIMER = (
    "This supports self-awareness and is not a medical diagnosis. "
    "If you're struggling, consider talking to someone you trust or a professional."
)


@dataclass
class ModalityResult:
    name: str  # "text" | "acoustic" | "visual"
    score: Optional[float]  # 0-1 calibrated-ish probability, None when unavailable
    confidence: float  # 0-1
    available: bool
    label: str = ""  # Low | Moderate | High | Unknown
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FusedResult:
    final_score: Optional[float]
    level: str  # Low | Moderate | High | Uncertain
    confidence: float
    contributions: Dict[str, float]  # modality -> normalized weight used
    insufficient_evidence: bool
    uncertainty_note: str
    modalities: Dict[str, ModalityResult] = field(default_factory=dict)


def _band(score: float) -> str:
    if score < 0.33:
        return "Low"
    if score < 0.60:
        return "Moderate"
    return "High"


def analyze_text(text: str) -> ModalityResult:
    """Text modality via the canonical contextual analyzer (same for typed
    and transcribed speech — see analyze_text_stress for the shared entry)."""
    from backend.app.services.voice_language import analyze_language

    if not (text or "").strip():
        return ModalityResult(name="text", score=None, confidence=0.1,
                              available=False, label="Unknown",
                              detail={"note": "No words captured."})
    lang = analyze_language(text)
    score = float(lang["language_score"])
    return ModalityResult(
        name="text", score=score, confidence=float(lang.get("confidence", 0.4)),
        available=True, label=_band(score),
        detail={"tags": lang.get("tags", []), "subject": lang.get("subject", "self"),
                "severe": bool(lang.get("severe", False)),
                "masking": bool(lang.get("masking", False))},
    )


def analyze_acoustic(audio_base64: Optional[str], sample_rate: int = 16000) -> ModalityResult:
    """Acoustic modality from raw audio. Unavailable (never faked) when no
    clear speech is present; quiet recordings get reduced confidence."""
    from backend.app.services import voice_service as vs

    if not audio_base64:
        return ModalityResult(name="acoustic", score=None, confidence=0.1,
                              available=False, label="Unknown",
                              detail={"note": "No audio provided."})
    try:
        vad = vs.detect_voice_activity(audio_base64, sample_rate)
    except Exception as e:
        return ModalityResult(name="acoustic", score=None, confidence=0.1,
                              available=False, label="Unknown",
                              detail={"note": f"Audio unreadable: {e}"})
    if not vad.get("voice_present"):
        return ModalityResult(
            name="acoustic", score=None,
            confidence=0.15, available=False, label="Unknown",
            detail={"note": "No clear speech in audio.",
                    "audio_level": vad.get("audio_level", "silent"),
                    "steady_noise": bool(vad.get("steady_noise", False))},
        )
    try:
        y, sr = vs._decode_audio(audio_base64)
        features = vs._extract_features(y, sr)
        pred = vs._predict_stress_from_features(features, vs.DEFAULT_CONFIG)
        score = float(pred["stress_score"])
        conf = float(pred["confidence"])
        level = vs.assess_audio_level(y)["level"]
        if level == "very_quiet":
            conf = max(0.15, conf * 0.5)
        elif level == "quiet":
            conf = max(0.15, conf * 0.75)
        return ModalityResult(
            name="acoustic", score=score, confidence=conf, available=True,
            label=_band(score),
            detail={"audio_level": level, "sad_tone": bool(pred.get("sad_tone", False))},
        )
    except Exception as e:
        return ModalityResult(name="acoustic", score=None, confidence=0.15,
                              available=False, label="Unknown",
                              detail={"note": f"Acoustic analysis failed: {e}"})


def wrap_visual(facial_score: Optional[float] = None,
                facial_confidence: Optional[float] = None,
                facial_level: Optional[str] = None) -> ModalityResult:
    """Wrap an EXISTING facial-pipeline output (never recomputed here).

    The webcam model is used only within its validated scope: pass through
    whatever the facial pipeline reported, or mark unavailable.
    """
    if facial_score is None:
        return ModalityResult(name="visual", score=None, confidence=0.1,
                              available=False, label="Unknown",
                              detail={"note": "No webcam reading provided."})
    try:
        s = float(facial_score)
        s = s / 100.0 if s > 1.0 else s
        s = max(0.0, min(1.0, s))
        conf = float(facial_confidence) if facial_confidence is not None else 0.7
        return ModalityResult(name="visual", score=s, confidence=max(0.05, min(1.0, conf)),
                              available=True, label=str(facial_level or _band(s)),
                              detail={"source": "existing facial pipeline"})
    except (TypeError, ValueError):
        return ModalityResult(name="visual", score=None, confidence=0.1,
                              available=False, label="Unknown",
                              detail={"note": "Invalid webcam reading."})


def fuse_modalities(modalities: List[ModalityResult]) -> FusedResult:
    """Confidence-aware fusion over available modalities only.

    Unavailable modalities contribute nothing (no fixed 0.5 filler). With no
    evidence at all the result is explicitly Uncertain.
    """
    usable = [m for m in modalities if m.available and m.score is not None]
    by_name = {m.name: m for m in modalities}
    if not usable:
        return FusedResult(
            final_score=None, level="Uncertain", confidence=0.15,
            contributions={}, insufficient_evidence=True,
            uncertainty_note=(
                "Not enough clear signal to estimate stress. "
                "Please speak for a few seconds near the mic and try again. " + DISCLAIMER
            ),
            modalities=by_name,
        )
    # Weight = confidence x decisiveness; floor keeps every available
    # modality in the mix without letting one dictate.
    raw: Dict[str, float] = {}
    for m in usable:
        w = max(0.05, m.confidence) * (0.5 + abs(float(m.score) - 0.5) * 2.0)
        raw[m.name] = w
    total = sum(raw.values())
    weights = {k: round(v / total, 3) for k, v in raw.items()}
    # Clamp: no single modality above 70% — only meaningful with 2+
    # modalities (a lone modality keeps weight 1.0, nothing to dilute it).
    if len(weights) > 1:
        for k in list(weights):
            if weights[k] > 0.70:
                excess = weights[k] - 0.70
                weights[k] = 0.70
                others = [o for o in weights if o != k]
                if others:
                    share = excess / len(others)
                    for o in others:
                        weights[o] = round(weights[o] + share, 3)
    final = round(sum(by_name[k].score * weights[k] for k in weights), 4)  # type: ignore[arg-type]
    conf = round(max(0.15, min(0.95, sum(by_name[k].confidence * weights[k] for k in weights))), 3)
    level = _band(final)
    if level == "High":
        note = ("Possible elevated stress — you may be feeling overwhelmed. " + DISCLAIMER)
    elif level == "Moderate":
        note = ("Some signs of strain. A short break or slow breaths may help. " + DISCLAIMER)
    else:
        note = ("No strong signs of stress in the available signals. " + DISCLAIMER)
    if conf < 0.35:
        note = "This reading is uncertain (weak signal). " + note
    return FusedResult(
        final_score=final, level=level, confidence=conf,
        contributions=weights, insufficient_evidence=False,
        uncertainty_note=note, modalities=by_name,
    )


def estimate(text: Optional[str] = None,
             audio_base64: Optional[str] = None,
             sample_rate: int = 16000,
             facial_score: Optional[float] = None,
             facial_confidence: Optional[float] = None,
             facial_level: Optional[str] = None) -> FusedResult:
    """One-call multimodal estimate across whatever inputs are available."""
    return fuse_modalities([
        analyze_text(text or ""),
        analyze_acoustic(audio_base64, sample_rate),
        wrap_visual(facial_score, facial_confidence, facial_level),
    ])
