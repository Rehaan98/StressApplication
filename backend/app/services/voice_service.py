"""
Voice Stress Analysis Service

Processes audio input to extract voice features and predict stress levels.
Used in multimodal fusion with webcam-based facial analysis.

Pipeline:
1. Audio decode → 2. Voice Activity Detection → 3. Feature Extraction → 4. Stress Prediction → 5. Output
"""

import base64
import io
import json
import math
import time
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import librosa

from backend.app.core.config import settings


# ---------------------------------------------------------------------------
# Voice Stress Thresholds (configurable)
# ---------------------------------------------------------------------------

STRESS_THRESHOLDS = {
    "low": 0.33,
    "moderate": 0.60,
}

# Conversation flow questions (configurable)
VOICE_CONVERSATION_QUESTIONS = [
    "Hi. I'm here to help you understand how you're feeling today. There are no right or wrong answers. Just talk naturally.",
    "How have you been feeling lately?",
    "What has your day been like so far?",
    "How has your energy been recently?",
    "Have you been feeling under pressure recently?",
    "Is there anything that's been occupying your mind lately?",
    "How are you handling your current workload?",
    "How has your sleep been recently?",
    "When things become difficult, how do you usually feel?",
    "Do you find yourself worrying about things more than usual?",
    "Thank you for talking with me. Based on our conversation, I've generated a stress assessment.",
]

# Default configuration
DEFAULT_CONFIG = {
    "WEBCAM_WEIGHT": 0.5,
    "VOICE_WEIGHT": 0.5,
    "MIN_CONFIDENCE": 0.3,
    "SPEECH_TIMEOUT": 5.0,
    "MAX_SESSION_DURATION": 300.0,
    # Fusion of acoustic voice score + spoken-words score.
    # Words carry slightly more weight so clearly distressed language
    # (sad, tired, unhappy, "very stressed") pushes past 60% → High.
    "VOICE_TEXT_FUSION_VOICE_W": 0.45,
    "VOICE_TEXT_FUSION_TEXT_W": 0.55,
}


# ---------------------------------------------------------------------------
# Spoken-words stress analysis (lexicon based, no extra ML deps)
# ---------------------------------------------------------------------------

_HIGH_STRESS_WORDS = {
    "stressed", "stress", "stressful", "overwhelmed", "overwhelm", "anxious",
    "anxiety", "panic", "panicking", "worried", "worry", "worrying", "fear",
    "afraid", "scared", "terrified", "dread", "desperate", "hopeless",
    "depressed", "depressing", "depression", "sad", "sadness", "unhappy",
    "miserable", "gloomy", "heartbroken", "despair", "tearful", "weepy",
    "crying", "cry", "cried", "angry", "anger",
    "furious", "frustrated", "frustrating", "irritated", "exhausted",
    "exhausting", "tired", "weary", "fatigued", "drained", "wiped",
    "burnout", "burned", "pressure", "deadline",
    "deadlines", "workload", "insomnia", "sleepless", "nightmare",
    "headache", "migraine", "tension", "tense", "nervous", "restless",
    "racing", "overthinking", "panic-attack", "breakdown", "crashed",
    "crashing", "awful", "terrible", "horrible", "hate", "stuck", "trapped",
    "lonely", "loneliness", "isolated", "suffering", "unbearable",
    "can't-cope", "cant-cope", "give-up", "breaking",
}

# Multi-word patterns that on their own signal strong distress.
# Matched against the lowercased transcript with spaces/punctuation normalized.
_SEVERE_PHRASES = (
    "very stressed",
    "so stressed",
    "really stressed",
    "extremely stressed",
    "super stressed",
    "too stressed",
    "very sad",
    "so sad",
    "really sad",
    "feeling sad",
    "feel sad",
    "feeling tired",
    "feel tired",
    "so tired",
    "very tired",
    "really tired",
    "feeling unhappy",
    "feel unhappy",
    "very unhappy",
    "so unhappy",
    "feeling overwhelmed",
    "feel overwhelmed",
    "so overwhelmed",
    "can't cope",
    "cannot cope",
    "cant cope",
    "breaking down",
    "mental breakdown",
    "need help",
    "help me",
    "what should i do",
    "what do i do",
    "can't sleep",
    "cannot sleep",
    "cant sleep",
    "no sleep",
    "haven't slept",
    "have not slept",
    "crying all",
    "cry all",
    "give up",
    "hopeless",
)

# Help-seeking language: user is asking what to do → treat as elevated
# and make sure coping suggestions are emphasized.
_HELP_PHRASES = (
    "what should i do",
    "what do i do",
    "help me",
    "need help",
    "any advice",
    "how do i",
    "how can i",
    "please help",
)

_MODERATE_WORDS = {
    "busy", "tough", "hard", "difficult", "hectic", "rushed", "behind",
    "tiring", "drained", "low", "down", "off", "meh", "worry", "concern",
    "concerned", "uneasy", "bothered", "annoyed", "grumpy", "moody",
    "sigh", "ugh", "deadline", "exam", "exams", "interview", "meeting",
    "boss", "overtime",
}

_CALM_WORDS = {
    "calm", "relaxed", "relaxing", "peaceful", "peace", "rested", "restful",
    "refreshed", "great", "good", "fine", "okay", "happy", "joy", "joyful",
    "excited", "grateful", "thankful", "confident", "control", "balanced",
    "manageable", "sleeping-well", "energized", "hopeful", "optimistic",
    "laugh", "laughing", "smile", "smiling", "love", "loved",
}

_AMPLIFIERS = {
    "very", "so", "really", "extremely", "super", "too", "totally",
    "completely", "utterly", "incredibly", "always", "never", "constantly",
    "nonstop", "overwhelmingly",
}

_PHYSICAL_WORDS = {
    "headache", "migraine", "chest", "tight", "knot", "stomach", "nausea",
    "dizzy", "sweating", "sweaty", "shaking", "trembling", "heartbeat",
    "heart-racing", "breathless", "can't-breathe", "exhausted", "fatigue",
    "pain", "ache", "sore",
}

_SLEEP_WORDS = {"sleep", "slept", "insomnia", "sleepless", "awake", "night", "tired", "exhausted", "yawn"}
_WORK_WORDS = {"work", "job", "boss", "deadline", "meeting", "exam", "study", "overtime", "workload", "shift"}

_EMOTION_KEYWORDS = {
    "anger": {"angry", "anger", "furious", "frustrated", "irritated", "annoyed", "rage", "hate"},
    "fear": {"afraid", "scared", "fear", "anxious", "anxiety", "panic", "worried", "nervous", "dread"},
    "sadness": {"sad", "sadness", "unhappy", "miserable", "depressed", "depression", "hopeless", "lonely", "loneliness", "crying", "cry", "cried", "tearful", "down", "empty", "grief", "heartbroken", "despair", "tired", "weary", "exhausted", "drained"},
    "joy": {"happy", "joy", "great", "excited", "grateful", "love", "laugh", "relaxed", "calm"},
    "surprise": {"shocked", "surprised", "sudden", "unexpected", "overwhelmed"},
}


def _classify_score(score: float) -> str:
    if score < STRESS_THRESHOLDS["low"]:
        return "Low"
    if score < STRESS_THRESHOLDS["moderate"]:
        return "Moderate"
    return "High"


def fuse_voice_text(
    acoustic: float,
    acoustic_conf: float,
    lang: float,
    lang_conf: float,
    base_voice_w: float = 0.45,
    base_text_w: float = 0.55,
) -> Dict[str, float]:
    """Confidence-aware fusion of voice-tone and words scores.

    A low-confidence (or neutral, low-decisiveness) modality must not cancel
    strong evidence from the other one: each weight scales with
    confidence × decisiveness (|score − 0.5|), then is clamped so neither
    signal is ever ignored outright.
    """
    acoustic = max(0.0, min(1.0, float(acoustic)))
    lang = max(0.0, min(1.0, float(lang)))
    w_ac = max(0.05, float(acoustic_conf)) * (0.5 + abs(acoustic - 0.5) * 2.0)
    w_tx = max(0.05, float(lang_conf)) * (0.5 + abs(lang - 0.5) * 2.0)
    # Start from the calibrated base mix, then nudge by evidence strength.
    w_ac *= base_voice_w / 0.5
    w_tx *= base_text_w / 0.5
    total = w_ac + w_tx
    w_ac_n, w_tx_n = w_ac / total, w_tx / total
    # Clamp: neither modality may dominate completely nor vanish.
    w_tx_n = max(0.30, min(0.70, w_tx_n))
    w_ac_n = 1.0 - w_tx_n
    fused = w_ac_n * acoustic + w_tx_n * lang
    return {
        "fused": round(max(0.0, min(1.0, fused)), 4),
        "voice_weight": round(w_ac_n, 3),
        "text_weight": round(w_tx_n, 3),
    }


def analyze_text_stress(transcript: Optional[str]) -> Dict[str, Any]:
    """Score stress from words — typed or transcribed, SAME function.

    Delegates to the contextual analyzer in voice_language so identical text
    always yields identical scores no matter how it entered the system.
    Return shape is kept stable for existing callers.
    """
    from backend.app.services.voice_language import analyze_language

    text = (transcript or "").strip()
    if not text:
        return {
            "text_score": 0.5,
            "text_level": "Moderate",
            "confidence": 0.15,
            "keywords": [],
            "emotion_hint": "",
            "usable": False,
            "severe": False,
            "help_seeking": False,
            "counts": {"high": 0, "moderate": 0, "calm": 0, "physical": 0},
            "note": "Not enough speech to judge words — score uses voice tone only.",
        }

    lang = analyze_language(text)
    return {
        "text_score": float(lang["language_score"]),
        "text_level": str(lang["language_level"]),
        "confidence": float(lang["confidence"]),
        "keywords": list(lang.get("keywords", [])),
        "emotion_hint": str(lang.get("emotion_hint") or ""),
        "usable": bool(lang.get("usable", True)),
        "severe": bool(lang.get("severe", False)),
        "severe_phrases": list(lang.get("severe_phrases", [])),
        "help_seeking": bool(lang.get("help_seeking", False)),
        "counts": dict(lang.get("counts", {"high": 0, "calm": 0})),
        "tags": list(lang.get("tags", [])),
        "subject": str(lang.get("subject", "self")),
    }


_rag_engine_singleton: Any = None


def _retrieve_voice_interventions(
    stress_level: str,
    transcript: str,
    emotion_hint: str,
    voice_features: Dict[str, float],
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """Best-effort retrieval of coping treatments; never raises."""
    try:
        global _rag_engine_singleton
        if _rag_engine_singleton is None:
            from ml_engine.src.rag_engine import StressRAGEngine

            _rag_engine_singleton = StressRAGEngine()
        engine = _rag_engine_singleton
        # Map strongest voice features to pseudo-drivers for retrieval
        top_feats = sorted(voice_features.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
        drivers = [{"feature": k, "value": v} for k, v in top_feats]
        results = engine.retrieve_interventions(
            stress_level=stress_level,
            top_shap_drivers=drivers,
            user_query=transcript or "",
            top_k=top_k,
            emotion=emotion_hint or "",
        )
        # Keep only JSON-safe fields the frontend needs
        cleaned = []
        for r in results or []:
            cleaned.append(
                {
                    "id": str(r.get("id", "")),
                    "category": str(r.get("category", "")),
                    "title": str(r.get("title", "")),
                    "summary": str(r.get("summary", "")),
                    "protocol": [str(s) for s in (r.get("protocol", []) or [])][:6],
                    "evidence_base": str(r.get("evidence_base", "")),
                    "difficulty": str(r.get("difficulty", "")),
                    "duration_min": int(r.get("duration_min", 0) or 0),
                    "relevance_score": float(r.get("relevance_score", 0) or 0),
                }
            )
        return cleaned
    except Exception as e:
        print(f"[VoiceService] intervention retrieval skipped: {e}")
        return []


# ---------------------------------------------------------------------------
# Audio Decoding
# ---------------------------------------------------------------------------

def _strip_data_url_prefix(audio_base64: str) -> str:
    """Allow callers to send either raw base64 or a data URL."""
    if not audio_base64:
        return audio_base64
    s = audio_base64.strip()
    if "," in s and s.startswith("data:"):
        return s.split(",", 1)[1]
    return s


def _decode_with_ffmpeg(raw: bytes) -> Tuple[np.ndarray, int]:
    """Decode arbitrary containers (webm/opus, mp4, etc.) via ffmpeg to 16k mono PCM."""
    import subprocess
    import tempfile
    import os
    import soundfile as sf

    with tempfile.NamedTemporaryFile(suffix=".in", delete=False) as f_in:
        f_in.write(raw)
        in_path = f_in.name
    out_path = in_path + ".wav"
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                in_path,
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "wav",
                out_path,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        y, sr = sf.read(out_path, dtype="float32")
        if y.ndim > 1:
            y = np.mean(y, axis=1)
        return y.astype(np.float32), int(sr)
    finally:
        for p in (in_path, out_path):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass


def _decode_audio(audio_base64: str) -> Tuple[np.ndarray, int]:
    """Decode base64 audio to numpy array and sample rate.

    Frontend sends WAV (preferred) but older clients send webm/opus.
    We try librosa/soundfile first, then fall back to ffmpeg.
    """
    try:
        clean = _strip_data_url_prefix(audio_base64)
        if not clean:
            raise ValueError("empty audio payload")
        try:
            raw = base64.b64decode(clean, validate=True)
        except Exception:
            # Be lenient with non-validated payloads (e.g. newlines)
            raw = base64.b64decode(clean)
        if len(raw) < 500:
            raise ValueError(f"audio payload too small ({len(raw)} bytes)")
        # 1) Try direct decode (WAV/FLAC/OGG via soundfile)
        try:
            y, sr = librosa.load(io.BytesIO(raw), sr=None, mono=True)
            if y is not None and len(y) > 0:
                return y, int(sr)
        except Exception as direct_err:
            print(f"[VoiceService] direct decode failed, trying ffmpeg: {direct_err}")
        # 2) Fallback: ffmpeg transcode (handles webm/opus from MediaRecorder)
        y, sr = _decode_with_ffmpeg(raw)
        if y is None or len(y) == 0:
            raise ValueError("ffmpeg produced empty audio")
        return y, int(sr)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to decode audio: {e}")


# ---------------------------------------------------------------------------
# Audio level assessment (quiet-voice handling)
# ---------------------------------------------------------------------------
# RMS reference points (16-bit-normalized float audio, peak 1.0):
#   * ABSOLUTE_SILENCE_FLOOR — below this there is no usable speech energy;
#     treating it as voice previously let faint mic hiss score as stress.
#   * QUIET_THRESHOLD — speech is present but near the noise floor: keep it
#     (never cut off soft first/last words) yet distrust the acoustic reading
#     and ask the user to move closer.
# Levels are deliberately coarse ("silent" | "very_quiet" | "quiet" |
# "normal" | "loud") so the UI can show honest guidance instead of a fake %.
ABSOLUTE_SILENCE_FLOOR = 0.002
QUIET_THRESHOLD = 0.015
LOUD_THRESHOLD = 0.35


def assess_audio_level(y: "np.ndarray") -> Dict[str, Any]:
    """Coarse, honest recording-level assessment from raw PCM. Never raises."""
    try:
        import numpy as _np

        if y is None or len(y) == 0:
            return {"level": "silent", "rms": 0.0, "peak": 0.0,
                    "clipping_ratio": 0.0, "usable": False}
        rms = float(_np.sqrt(_np.mean(_np.square(y.astype(_np.float64)))))
        peak = float(_np.max(_np.abs(y))) if len(y) else 0.0
        clipping = float(_np.mean(_np.abs(y) > 0.99))
        if rms < ABSOLUTE_SILENCE_FLOOR:
            level = "silent"
        elif rms < QUIET_THRESHOLD:
            level = "very_quiet"
        elif rms > LOUD_THRESHOLD:
            level = "loud"
        else:
            # Soft-but-clear band: above the floor yet quiet speech.
            level = "normal" if rms >= 0.05 else "quiet"
        return {"level": level, "rms": round(rms, 5), "peak": round(peak, 4),
                "clipping_ratio": round(clipping, 4),
                "usable": level not in ("silent",)}
    except Exception:
        return {"level": "silent", "rms": 0.0, "peak": 0.0,
                "clipping_ratio": 0.0, "usable": False}

# ---------------------------------------------------------------------------
# Voice Activity Detection (VAD)
# ---------------------------------------------------------------------------

def detect_voice_activity(audio_base64: str, sample_rate: int = 16000) -> Dict[str, Any]:
    """Detect if the audio contains speech/voice.

    Two-stage gate (fixes faint-hiss false positives):
      1. ABSOLUTE floor — recordings below the silence floor are never voice,
         no matter what the relative threshold says.
      2. Relative adaptive threshold (mean + 0.5*std) for genuine speech, plus
         a flatness check: steady background noise with almost no variation is
         not speech even when loud enough.
    Quiet-but-real speech still passes (soft first/last words are preserved);
    callers should read ``audio_level`` to decide whether to ask the user to
    move closer to the mic.
    """
    try:
        y, sr = _decode_audio(audio_base64)

        if sr != sample_rate:
            y = librosa.resample(y, orig_sr=sr, target_sr=sample_rate)
            sr = sample_rate

        level_info = assess_audio_level(y)

        frame_size = int(sample_rate * 0.025)
        hop_length = int(sample_rate * 0.010)

        rms = librosa.feature.rms(y=y, frame_length=frame_size, hop_length=hop_length)[0]

        # Use adaptive threshold: mean + 0.5*std captures typical speech energy
        rms_mean = float(np.mean(rms))
        rms_std = float(np.std(rms))
        threshold = rms_mean + 0.5 * rms_std
        speech_frames = rms > threshold
        total_frames = len(rms)
        speech_ratio = float(np.sum(speech_frames)) / total_frames if total_frames > 0 else 0.0

        # Flatness: real speech varies (measured cv >= 0.20 for soft/breathy/
        # pause-heavy speech); steady hiss/fan noise sits at cv ~= 0.04.
        # The 0.12 gate below was set from those measurements, not guessed.
        cv = (rms_std / rms_mean) if rms_mean > 1e-9 else 0.0
        looks_like_steady_noise = bool(
            level_info["level"] in ("silent", "very_quiet") and cv < 0.12
        )

        # More lenient: voice present if >10% of frames exceed threshold
        relative_voice = speech_ratio > 0.10
        voice_present = bool(
            relative_voice
            and level_info["usable"]
            and not looks_like_steady_noise
        )

        return {
            "voice_present": voice_present,
            "speech_ratio": round(speech_ratio, 4),
            "duration_seconds": round(len(y) / sample_rate, 2),
            "rms_mean": round(float(np.mean(rms)), 4),
            "rms_std": round(float(np.std(rms)), 4),
            "audio_level": level_info["level"],
            "audio_rms": level_info["rms"],
            "clipping_ratio": level_info["clipping_ratio"],
            "steady_noise": looks_like_steady_noise,
        }
    except Exception as e:
        print(f"[VoiceService] VAD error: {e}")
        return {
            "voice_present": False,
            "speech_ratio": 0.0,
            "duration_seconds": 0.0,
            "rms_mean": 0.0,
            "rms_std": 0.0,
            "audio_level": "silent",
            "audio_rms": 0.0,
            "clipping_ratio": 0.0,
            "steady_noise": False,
            "decode_error": str(e)[:120],
        }


# ---------------------------------------------------------------------------
# Voice Feature Extraction
# ---------------------------------------------------------------------------

def _extract_features(y: np.ndarray, sr: int) -> Dict[str, float]:
    """Extract voice features for stress analysis."""
    features: Dict[str, float] = {}

    try:
        # 1. Pitch features
        y_harmonic, _ = librosa.effects.hpss(y)
        pitches, magnitudes = librosa.piptrack(y=y_harmonic, sr=sr)
        pitch_valid = pitches > 0
        pitch_mean = float(np.mean(pitches[pitch_valid])) if np.any(pitch_valid) else 0.0
        pitch_std = float(np.std(pitches[pitch_valid])) if np.any(pitch_valid) else 0.0
        pitch_range = float(np.max(pitches[pitch_valid]) - np.min(pitches[pitch_valid])) if np.any(pitch_valid) else 0.0
        features["pitch_mean"] = pitch_mean
        features["pitch_std"] = pitch_std
        features["pitch_range"] = pitch_range

        # Guard: if no pitch detected, set jitter and pitch_variation to 0
        if pitch_mean == 0.0:
            features["pitch_variation"] = 0.0  # will be computed later with guard
        else:
            pitch_variation_raw = pitch_range / max(pitch_mean, 1e-4)

        # 2. Energy features
        rms = librosa.feature.rms(y=y)[0]
        features["energy_mean"] = float(np.mean(rms))
        features["energy_std"] = float(np.std(rms))
        energy_threshold = np.percentile(rms, 30)
        silence_frames = np.sum(rms < energy_threshold)
        total_frames = len(rms)
        features["speech_silence_ratio"] = silence_frames / total_frames if total_frames > 0 else 0.0

        # 3. Zero-crossing rate
        zcr = librosa.feature.zero_crossing_rate(y)[0]
        features["zcr_mean"] = float(np.mean(zcr))

        # 4. Spectral features
        spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        features["spectral_centroid_mean"] = float(np.mean(spectral_centroids))
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
        features["spectral_bandwidth_mean"] = float(np.mean(spectral_bandwidth))
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
        features["spectral_rolloff_mean"] = float(np.mean(spectral_rolloff))

        # 5. MFCC features
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        for i in range(13):
            features[f"mfcc_{i+1}"] = float(np.mean(mfccs[i]))

        # 6. Jitter
        if pitch_mean > 50 and pitch_mean != 0.0:
            voiced_mask = pitches > 50
            if np.sum(voiced_mask) > 10:
                pitch_contour = pitches[voiced_mask]
                if len(pitch_contour) > 1:
                    diffs = np.diff(pitch_contour)
                    features["jitter"] = float(np.mean(np.abs(diffs))) / max(pitch_mean, 1e-4)
                else:
                    features["jitter"] = 0.0
            else:
                features["jitter"] = 0.0
        else:
            features["jitter"] = 0.0

        # 7. Shimmer
        features["shimmer"] = features.get("energy_std", 0.0) / max(features.get("energy_mean", 1e-4), 1e-4)

    except Exception as e:
        print(f"[VoiceService] Feature extraction warning: {e}")

    return features


# ---------------------------------------------------------------------------
# Voice Stress Prediction
# ---------------------------------------------------------------------------

def _predict_stress_from_features(
    features: Dict[str, float],
    config: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Predict stress level from extracted voice features."""
    if config is None:
        config = DEFAULT_CONFIG

    pitch_mean = features.get("pitch_mean", 0.0)
    pitch_std = features.get("pitch_std", 0.0)
    pitch_range = features.get("pitch_range", 0.0)
    energy_mean = features.get("energy_mean", 0.0)
    energy_std = features.get("energy_std", 0.0)
    speech_silence_ratio = features.get("speech_silence_ratio", 0.0)
    zcr_mean = features.get("zcr_mean", 0.0)
    spectral_centroid_mean = features.get("spectral_centroid_mean", 0.0)
    mfcc_1_mean = features.get("mfcc_1", 0.0)
    jitter = features.get("jitter", 0.0)
    shimmer = features.get("shimmer", 0.0)

    # Stress indicators
    pitch_variation = pitch_range / max(pitch_mean, 1e-4)
    indicator1 = min(pitch_variation * 0.3, 1.0)

    normalized_pitch = pitch_mean / 300.0
    indicator2 = min(max((normalized_pitch - 1.0) * 0.2, 0.0), 1.0) if normalized_pitch > 1.0 else 0.0

    energy_variability = energy_std / max(energy_mean, 1e-4)
    indicator3 = min(energy_variability * 0.4, 1.0)

    indicator4 = min(speech_silence_ratio * 0.5, 1.0)
    indicator5 = min(zcr_mean * 10, 1.0)
    indicator6 = min(spectral_centroid_mean / 4000.0, 1.0)
    indicator7 = min(abs(mfcc_1_mean) * 2, 1.0)
    indicator8 = min(jitter * 5, 1.0)
    indicator9 = min(shimmer * 3, 1.0)

    weights = {
        "pitch_variation": 0.15,
        "pitch_mean": 0.15,
        "energy_variability": 0.15,
        "speech_silence_ratio": 0.10,
        "zcr": 0.10,
        "spectral_centroid": 0.08,
        "mfcc_1": 0.07,
        "jitter": 0.10,
        "shimmer": 0.10,
    }

    stress_score = (
        indicator1 * weights["pitch_variation"]
        + indicator2 * weights["pitch_mean"]
        + indicator3 * weights["energy_variability"]
        + indicator4 * weights["speech_silence_ratio"]
        + indicator5 * weights["zcr"]
        + indicator6 * weights["spectral_centroid"]
        + indicator7 * weights["mfcc_1"]
        + indicator8 * weights["jitter"]
        + indicator9 * weights["shimmer"]
    )

    stress_score = max(0.0, min(1.0, stress_score))

    # Sad / flat-affect voice: low-pitched, subdued and monotonous speech is
    # a classic low-arousal distress pattern (sadness, tiredness, depression).
    # The indicators above mostly catch high-arousal stress (fast, variable,
    # tense), so an explicitly sad-sounding tone is lifted to ~60%+ here.
    # Gates are deliberately relative (flat delivery + subdued level) so this
    # also fires at normal mic volumes, not just near-silent recordings.
    # Note: very quiet speech may yield no trackable pitch (pitch_mean == 0);
    # if the signal is still voiced (low zero-crossing rate) we treat that
    # as flat/quiet rather than as "no pitch".
    # Floor guard: near-silence energy (background hiss) must never trigger
    # the sad-voice lift — quietness alone is not evidence of distress.
    _audible = bool(energy_mean >= ABSOLUTE_SILENCE_FLOOR)
    _low_pitch = 50.0 < pitch_mean < 200.0
    if pitch_mean <= 50.0 and energy_mean < 0.04 and zcr_mean < 0.03 and pitch_mean >= 0.0:
        _low_pitch = _audible
    sad_tone = bool(
        _audible
        and _low_pitch
        and energy_mean < 0.12
        and pitch_variation < 1.0
        and energy_variability < 1.0
    )
    if sad_tone:
        stress_score = max(stress_score, 0.62)

    if stress_score < STRESS_THRESHOLDS["low"]:
        stress_level = "Low"
    elif stress_score < STRESS_THRESHOLDS["moderate"]:
        stress_level = "Moderate"
    else:
        stress_level = "High"

    confidence = min(
        1.0,
        0.4 + 0.4 * min(speech_silence_ratio, 1.0) + 0.2 * min(pitch_mean / 200.0, 1.0),
    )
    confidence = max(0.2, min(1.0, confidence))

    return {
        "stress_score": round(stress_score, 4),
        "confidence": round(confidence, 4),
        "stress_level": stress_level,
        "features": features,
        "voice_features": features,
        "sad_tone": sad_tone,
    }


# ---------------------------------------------------------------------------
# Main Analysis Entry Point
# ---------------------------------------------------------------------------

def analyze_voice_stress(
    audio_base64: str,
    sample_rate: int = 16000,
    config: Dict[str, Any] = None,
    transcript: Optional[str] = None,
) -> Dict[str, Any]:
    """Full pipeline: VAD → acoustic features → words analysis → fused stress → coping suggestions."""
    if config is None:
        config = DEFAULT_CONFIG

    vad_result = detect_voice_activity(audio_base64, sample_rate)
    text_result = analyze_text_stress(transcript)

    if not vad_result["voice_present"]:
        usable_text = bool(text_result.get("usable"))
        if not usable_text and vad_result.get("decode_error"):
            # Honest failure beats a fabricated 0.5: the audio could not be
            # read at all and there are no words to fall back on.
            raise ValueError(
                "Could not read the audio recording. Please record again, "
                "speak closer to the microphone, and try again."
            )
        if usable_text:
            fallback_score = float(text_result["text_score"])
            fallback_level = str(text_result["text_level"])
            confidence = float(text_result["confidence"]) * 0.6
            insufficient = False
            explanation = (
                "We couldn't hear clear speech in the audio, so this uses your words only. "
                "Try speaking closer to the mic for a full voice-tone reading."
            )
        else:
            # No usable evidence in EITHER modality: return a neutral
            # placeholder explicitly flagged as insufficient — never a
            # confident-sounding Low/Moderate verdict.
            fallback_score = 0.5
            fallback_level = _classify_score(0.5)
            confidence = 0.15
            insufficient = True
            if vad_result.get("steady_noise"):
                explanation = (
                    "We heard only steady background noise, not speech. Please move somewhere "
                    "quieter, speak closer to the microphone, and try again."
                )
            elif vad_result.get("audio_level") in ("silent", "very_quiet"):
                explanation = (
                    "Your voice was too quiet to analyze reliably. Please move closer to the "
                    "microphone or speak a little louder, then try again. We never guess "
                    "from silence."
                )
            else:
                explanation = (
                    "No detectable speech in the audio and no words to read. "
                    "Please speak for a few seconds and try again."
                )
        interventions = _retrieve_voice_interventions(
            fallback_level if not insufficient else "Moderate",
            (transcript or ""), str(text_result.get("emotion_hint") or ""), {}, top_k=3,
        )
        return {
            "stress_score": round(fallback_score, 4),
            "voice_score": 0.5,
            "text_score": float(text_result["text_score"]),
            "confidence": round(confidence, 4),
            "stress_level": fallback_level,
            "voice_features": {},
            "features": {},
            "vad": vad_result,
            "transcript": (transcript or "").strip(),
            "text_keywords": text_result.get("keywords", []),
            "emotion_hint": text_result.get("emotion_hint", ""),
            "explanation": explanation,
            "interventions": interventions,
            "note": explanation,
            "insufficient_evidence": insufficient,
            "voice_available": False,
            "audio_level": vad_result.get("audio_level", "silent"),
            "quiet_warning": (
                "Your voice sounds very quiet — move closer to the mic for a fuller reading."
                if vad_result.get("audio_level") in ("quiet", "very_quiet") else None
            ),
        }

    y, sr = _decode_audio(audio_base64)
    level_info = assess_audio_level(y)
    audio_level = str(level_info.get("level", "normal"))
    features = _extract_features(y, sr)
    prediction = _predict_stress_from_features(features, config)
    voice_score = float(prediction["stress_score"])
    voice_conf = float(prediction["confidence"])
    # Near-floor audio keeps its words but its TONE reading is distrusted:
    # quietness alone must never drive the verdict. The confidence-aware
    # fusion below then leans on the words automatically.
    if audio_level == "very_quiet":
        voice_conf = max(0.15, voice_conf * 0.5)
    elif audio_level == "quiet":
        voice_conf = max(0.15, voice_conf * 0.75)
    quiet_warning = (
        "Your voice sounds very quiet — the tone reading counts less here; "
        "move closer to the mic for a fuller analysis."
        if audio_level in ("quiet", "very_quiet") else None
    )

    text_score = float(text_result["text_score"])
    text_usable = bool(text_result.get("usable"))
    text_conf = float(text_result.get("confidence", 0.3)) if text_usable else 0.15
    severe_words = bool(text_result.get("severe")) if text_usable else False
    help_seeking = bool(text_result.get("help_seeking")) if text_usable else False
    sad_tone = bool(prediction.get("sad_tone", False))
    w_voice = float(config.get("VOICE_TEXT_FUSION_VOICE_W", 0.45))
    w_text = float(config.get("VOICE_TEXT_FUSION_TEXT_W", 0.55))
    fusion_weights = {"voice_weight": w_voice, "text_weight": w_text}
    if text_usable:
        # Confidence-aware fusion: a low-confidence or near-neutral modality
        # cannot cancel strong evidence from the other one.
        fused = fuse_voice_text(voice_score, voice_conf, text_score, text_conf, w_voice, w_text)
        combined = fused["fused"]
        fusion_weights = {"voice_weight": fused["voice_weight"], "text_weight": fused["text_weight"]}
        confidence = max(
            0.2,
            min(1.0, fusion_weights["voice_weight"] * voice_conf + fusion_weights["text_weight"] * text_conf),
        )
    else:
        combined = voice_score
        confidence = voice_conf
    # Severity floors: clearly distressed language or a sad-sounding tone
    # must land at 60%+ (High), never diluted back to Moderate/Low.
    if text_usable and severe_words:
        combined = max(combined, 0.66)
        confidence = max(confidence, 0.65)
    elif text_usable and help_seeking:
        combined = max(combined, 0.62)
        confidence = max(confidence, 0.6)
    counts = text_result.get("counts", {}) or {}
    calm_words = int(counts.get("calm", 0) or 0)
    high_words = int(counts.get("high", 0) or 0)
    # Calm veto: explicitly calm/positive words with no distress words
    # overrule a flat-sounding tone (soft voice ≠ sad voice).
    calm_veto = bool(text_usable and calm_words >= 1 and high_words == 0 and not severe_words)
    if sad_tone and not calm_veto and (not text_usable or text_score >= 0.25):
        combined = max(combined, 0.61)
        confidence = max(confidence, 0.55)
    combined = max(0.0, min(1.0, combined))
    level = _classify_score(combined)

    keywords = text_result.get("keywords", [])
    emotion_hint = str(text_result.get("emotion_hint") or "")
    interventions = _retrieve_voice_interventions(level, (transcript or ""), emotion_hint, features, top_k=3)

    if text_usable:
        parts = [
            f"Voice tone scored {voice_score:.0%} and your words scored {text_score:.0%}"
            + (f" (keywords: {', '.join(keywords[:5])})" if keywords else "")
            + f". Combined: {combined:.0%} → {level}."
        ]
        if sad_tone:
            parts.append("Your voice sounds flat and low-energy (sad-leaning), which raises the score.")
        if severe_words:
            parts.append("Your words express strong distress, so the result stays High.")
        elif help_seeking:
            parts.append("You're asking what to do — the coping suggestions below are picked for that.")
        if quiet_warning:
            parts.append(
                "Your voice was quiet, so the tone reading counts less than your words here."
            )
        explanation = " ".join(parts)
    elif sad_tone:
        explanation = (
            f"Your voice sounds flat and low-energy (sad-leaning), scoring {voice_score:.0%} → {level}. "
            "Speak a full sentence next time for a voice + words reading."
        )
    else:
        explanation = (
            f"Not enough words to judge language, so this uses voice tone only ({voice_score:.0%} → {level}). "
            "Speak a full sentence next time for a voice + words reading."
        )

    prediction["voice_score"] = round(voice_score, 4)
    prediction["text_score"] = round(text_score, 4)
    prediction["voice_confidence"] = round(max(0.0, min(1.0, voice_conf)), 4)
    prediction["text_confidence"] = round(max(0.0, min(1.0, text_conf if text_usable else 0.15)), 4)
    prediction["fusion_weights"] = fusion_weights
    prediction["stress_score"] = round(combined, 4)
    prediction["stress_level"] = level
    prediction["confidence"] = round(confidence, 4)
    prediction["vad"] = vad_result
    prediction["audio_duration"] = vad_result["duration_seconds"]
    prediction["transcript"] = (transcript or "").strip()
    prediction["text_keywords"] = keywords
    prediction["emotion_hint"] = emotion_hint
    prediction["explanation"] = explanation
    prediction["interventions"] = interventions
    prediction["insufficient_evidence"] = False
    prediction["voice_available"] = True
    prediction["audio_level"] = audio_level
    prediction["quiet_warning"] = quiet_warning
    # Keep both keys for backwards-compat with API layer
    prediction["voice_features"] = prediction.get("voice_features", features)
    prediction["features"] = prediction.get("features", features)

    return prediction


# ---------------------------------------------------------------------------
# Conversation Management
# ---------------------------------------------------------------------------

class ConversationManager:
    """Manages the conversation flow for voice assessment."""
    
    def __init__(self, session_id: str, config: Dict[str, Any] = None):
        self.session_id = session_id
        self.config = config or DEFAULT_CONFIG
        self.questions = self.config.get("questions", VOICE_CONVERSATION_QUESTIONS)
        self.turn_count = 0
        self.max_turns = 8
        self.start_time = time.time()
        self.turns: List[Dict[str, Any]] = []
    
    def get_next_question(self, previous_response: str = None) -> Optional[str]:
        if self.turn_count >= len(self.questions) or self.turn_count >= self.max_turns:
            return None
        question = self.questions[self.turn_count]
        self.turn_count += 1
        return question
    
    def record_turn(self, turn_data: Dict[str, Any]) -> None:
        self.turns.append(turn_data)
    
    def should_continue(self) -> bool:
        return (
            self.turn_count < self.max_turns
            and self.turn_count < len(self.questions)
            and (time.time() - self.start_time) < self.config.get("max_session_duration", 300.0)
        )
    
    def get_session_summary(self) -> Dict[str, Any]:
        avg_stress = 0.0
        if self.turns:
            scores = [t.get("user_stress_score", 0.0) for t in self.turns if t.get("user_stress_score") is not None]
            if scores:
                avg_stress = sum(scores) / len(scores)
        duration = time.time() - self.start_time
        return {
            "session_id": self.session_id,
            "total_turns": self.turn_count,
            "average_stress_score": round(avg_stress, 4),
            "duration_seconds": round(duration, 2),
            "stress_level": self._classify_level(avg_stress),
            "questions_asked": self.turn_count,
        }
    
    @staticmethod
    def _classify_level(avg_score: float) -> str:
        if avg_score < STRESS_THRESHOLDS["low"]:
            return "Low"
        elif avg_score < STRESS_THRESHOLDS["moderate"]:
            return "Moderate"
        else:
            return "High"


_converstation_instances: Dict[str, ConversationManager] = {}


def get_conversation_manager(session_id: str, config: Dict[str, Any] = None) -> ConversationManager:
    if session_id not in _converstation_instances:
        _converstation_instances[session_id] = ConversationManager(session_id, config)
    return _converstation_instances[session_id]


def reset_conversation_session(session_id: str) -> None:
    if session_id in _converstation_instances:
        del _converstation_instances[session_id]
