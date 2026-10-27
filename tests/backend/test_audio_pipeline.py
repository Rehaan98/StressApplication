"""
Audio pipeline regression tests — quiet-voice handling (spec sections 1-3).

Synthesized signals only (no fixtures, no randomness):
  normal / quiet / very_quiet / breathy / noisy-room / pause-heavy speech,
  steady hiss, fan-level noise, digital silence, undecodable payloads.

Asserts:
  * real speech passes VAD at every volume; noise/silence does not;
  * quietness alone never produces a High verdict;
  * identical words typed vs spoken agree within tolerance;
  * no-evidence input is flagged insufficient instead of a fake Low/Moderate;
  * undecodable audio with no words raises instead of returning 0.5.
"""

import base64
import io

import pytest
import numpy as np
import soundfile as sf
from httpx import AsyncClient

from backend.app.main import app
from backend.app.services import voice_service as vs


def synth(freq=160.0, amp=0.4, secs=5.0, sr=16000, noise=0.0, breathy=False,
          pauses=None, seed=0):
    t = np.arange(int(sr * secs)) / sr
    y = (amp * np.sin(2 * np.pi * freq * t)
         * (0.65 + 0.35 * np.sin(2 * np.pi * 2.5 * t))).astype(np.float32)
    if breathy:
        y = (y + 0.25 * amp * np.random.RandomState(seed).randn(len(y))).astype(np.float32)
    if noise > 0:
        y = (y + noise * np.random.RandomState(1).randn(len(y))).astype(np.float32)
    if pauses:
        for (a, b) in pauses:
            y[int(a * sr):int(b * sr)] = 0
    return y


def enc(y, sr=16000):
    buf = io.BytesIO()
    sf.write(buf, y, sr, format="WAV", subtype="PCM_16")
    return base64.b64encode(buf.getvalue()).decode()


SPEECH = {
    "normal": synth(amp=0.4),
    "quiet": synth(amp=0.05),
    "very_quiet": synth(amp=0.015),
    "breathy": synth(amp=0.03, breathy=True),
    "noisy_room": synth(amp=0.15, noise=0.06),
    "pause_heavy": synth(amp=0.25, pauses=[(1.0, 2.0), (3.0, 3.8)]),
}
NON_SPEECH = {
    "hiss": (0.0008 * np.random.RandomState(7).randn(16000 * 4)).astype(np.float32),
    "fan": (0.004 * np.random.RandomState(9).randn(16000 * 4)).astype(np.float32),
    "silence": np.zeros(16000 * 3, dtype=np.float32),
}

TEXT = "I feel so sad, feeling completely alone."


def test_vad_passes_quiet_speech():
    for name, y in SPEECH.items():
        vad = vs.detect_voice_activity(enc(y))
        assert vad["voice_present"] is True, f"{name} should pass VAD: {vad}"


def test_vad_rejects_noise_and_silence():
    for name, y in NON_SPEECH.items():
        vad = vs.detect_voice_activity(enc(y))
        assert vad["voice_present"] is False, f"{name} must not pass VAD: {vad}"


def test_audio_level_labels():
    assert vs.detect_voice_activity(enc(SPEECH["normal"]))["audio_level"] == "normal"
    assert vs.detect_voice_activity(enc(SPEECH["quiet"]))["audio_level"] == "quiet"
    assert vs.detect_voice_activity(enc(SPEECH["very_quiet"]))["audio_level"] == "very_quiet"
    assert vs.detect_voice_activity(enc(NON_SPEECH["silence"]))["audio_level"] == "silent"


def test_quietness_alone_never_high():
    for name in ("quiet", "very_quiet", "breathy"):
        r = vs.analyze_voice_stress(enc(SPEECH[name]), 16000,
                                    transcript="The meeting is at noon tomorrow.")
        assert r["stress_level"] != "High", (name, r)
        assert r.get("quiet_warning"), name  # user is told to move closer


def test_hiss_never_high_without_words():
    for name in ("hiss", "fan", "silence"):
        r = vs.analyze_voice_stress(enc(NON_SPEECH[name]), 16000, transcript="")
        assert r.get("insufficient_evidence") is True, name
        assert r["stress_level"] != "High", (name, r)
        assert r["confidence"] <= 0.2, (name, r)


def test_typed_spoken_parity_within_tolerance():
    typed = vs.analyze_text_stress(TEXT)["text_score"]
    for name, y in SPEECH.items():
        r = vs.analyze_voice_stress(enc(y), 16000, transcript=TEXT)
        assert abs(typed - r["stress_score"]) <= 0.12, (name, typed, r["stress_score"])
        assert r["stress_level"] == "High", (name, r)


def test_no_evidence_flagged_not_faked():
    r = vs.analyze_voice_stress(enc(NON_SPEECH["silence"]), 16000, transcript="")
    assert r["stress_score"] == 0.5
    assert r["stress_level"] == vs._classify_score(0.5)  # label matches score
    assert r["insufficient_evidence"] is True
    assert "guess" in r["explanation"].lower() or "try again" in r["explanation"].lower()


def test_undecodable_audio_raises():
    with pytest.raises(ValueError):
        vs.analyze_voice_stress(base64.b64encode(b"0" * 2000).decode(), 16000, transcript="")


def test_undecodable_audio_with_words_uses_text():
    r = vs.analyze_voice_stress(base64.b64encode(b"0" * 2000).decode(), 16000, transcript=TEXT)
    assert r["stress_level"] == "High"  # words carry the reading


@pytest.fixture(scope="module")
def event_loop():
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def auth_token():
    async with AsyncClient(app=app, base_url="http://test") as client:
        res = await client.post("/api/v1/auth/register", json={
            "email": "audiopipe@stressai.com",
            "full_name": "Audio Pipe",
            "password": "AudioPipe@2026",
        })
        if res.status_code != 201:
            res = await client.post("/api/v1/auth/login", json={
                "email": "audiopipe@stressai.com",
                "password": "AudioPipe@2026",
            })
        return res.json().get("access_token", "")


@pytest.mark.asyncio
async def test_api_surfaces_quiet_and_insufficient_flags(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.post("/api/v1/voice/analyze", json={
            "audio_base64": enc(SPEECH["very_quiet"]), "sample_rate": 16000,
            "transcript": "I feel tired.",
        }, headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["audio_level"] == "very_quiet"
        assert body["quiet_warning"]
        assert "insufficient_evidence" in body and "voice_available" in body

        r2 = await client.post("/api/v1/voice/analyze", json={
            "audio_base64": enc(NON_SPEECH["silence"]), "sample_rate": 16000,
        }, headers=headers)
        assert r2.status_code == 200, r2.text
        assert r2.json()["insufficient_evidence"] is True

        r3 = await client.post("/api/v1/voice/analyze", json={
            "audio_base64": base64.b64encode(b"0" * 2000).decode(), "sample_rate": 16000,
        }, headers=headers)
        assert r3.status_code == 400  # honest error, not a fake score
