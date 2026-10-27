"""
Stress-inference engine tests — modality separation, availability handling,
confidence-aware fusion, honest uncertainty (spec section 4).
"""

import base64
import io

import numpy as np
import soundfile as sf

from backend.app.services import stress_engine as se
from backend.app.services.stress_engine import (
    ModalityResult, analyze_text, analyze_acoustic, wrap_visual,
    fuse_modalities, estimate,
)


def enc(y, sr=16000):
    buf = io.BytesIO()
    sf.write(buf, y, sr, format="WAV", subtype="PCM_16")
    return base64.b64encode(buf.getvalue()).decode()


def speech(amp=0.3, secs=5.0):
    t = np.arange(int(16000 * secs)) / 16000
    return (amp * np.sin(2 * np.pi * 160 * t)
            * (0.65 + 0.35 * np.sin(2 * np.pi * 2.5 * t))).astype(np.float32)


def test_text_modality_matches_canonical_analyzer():
    from backend.app.services.voice_language import analyze_language
    text = "I feel so sad, feeling completely alone."
    mod = analyze_text(text)
    assert mod.available is True
    assert abs(mod.score - analyze_language(text)["language_score"]) < 1e-9
    assert analyze_text("").available is False
    assert analyze_text("   ").available is False


def test_acoustic_unavailable_without_speech():
    silence = enc(np.zeros(16000 * 2, dtype=np.float32))
    mod = analyze_acoustic(silence)
    assert mod.available is False
    assert mod.score is None
    assert analyze_acoustic(None).available is False
    assert analyze_acoustic("not-audio!!!").available is False


def test_acoustic_available_with_speech():
    mod = analyze_acoustic(enc(speech()))
    assert mod.available is True
    assert 0.0 <= mod.score <= 1.0


def test_visual_passthrough_only():
    assert wrap_visual().available is False
    m = wrap_visual(facial_score=75, facial_confidence=0.8, facial_level="High")
    assert m.available is True and abs(m.score - 0.75) < 1e-9
    assert wrap_visual(facial_score="junk").available is False


def test_fusion_ignores_unavailable_modalities():
    text_mod = analyze_text("I feel so sad, feeling completely alone.")
    off = ModalityResult(name="acoustic", score=None, confidence=0.1, available=False)
    fused = fuse_modalities([text_mod, off])
    assert fused.insufficient_evidence is False
    assert "acoustic" not in fused.contributions
    assert abs(fused.final_score - text_mod.score) < 1e-9


def test_fusion_no_evidence_is_uncertain():
    fused = fuse_modalities([
        ModalityResult(name="text", score=None, confidence=0.1, available=False),
        ModalityResult(name="acoustic", score=None, confidence=0.1, available=False),
    ])
    assert fused.insufficient_evidence is True
    assert fused.level == "Uncertain"
    assert fused.final_score is None
    assert "not a medical diagnosis" in fused.uncertainty_note.lower() or "diagnosis" in fused.uncertainty_note.lower()


def test_fusion_weights_sum_and_clamp():
    fused = fuse_modalities([
        ModalityResult(name="text", score=0.9, confidence=0.9, available=True),
        ModalityResult(name="acoustic", score=0.1, confidence=0.9, available=True),
    ])
    assert abs(sum(fused.contributions.values()) - 1.0) < 0.01
    assert max(fused.contributions.values()) <= 0.70


def test_estimate_end_to_end_text_only():
    fused = estimate(text="I feel so sad, feeling completely alone.")
    assert fused.level == "High"
    assert "overwhelm" in fused.uncertainty_note.lower() or "elevated" in fused.uncertainty_note.lower()


def test_estimate_nothing_is_uncertain():
    fused = estimate()
    assert fused.insufficient_evidence is True
    assert fused.level == "Uncertain"
