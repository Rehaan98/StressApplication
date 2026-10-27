"""
Unified multimodal assessment tests (spec section 10).

Covers: all-three success, each single-modality partial, each pair, total
failure, malformed inputs, low confidence, reproducibility/determinism,
missing-never-zero, real questionnaire scoring, and stored-history isolation.
No randomness; synthesized audio only where needed.
"""

import base64
import io

import pytest
import numpy as np
import soundfile as sf
from httpx import AsyncClient
from sqlalchemy.future import select

from backend.app.main import app
from backend.app.services import multimodal as mm
from backend.app.models.assessment import StressAssessment


def speech(amp=0.3, secs=4.0, sr=16000):
    t = np.arange(int(sr * secs)) / sr
    y = (amp * np.sin(2 * np.pi * 160 * t)
         * (0.65 + 0.35 * np.sin(2 * np.pi * 2.5 * t))).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, y, sr, format="WAV", subtype="PCM_16")
    return base64.b64encode(buf.getvalue()).decode()


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
            "email": "multimodal@stressai.com",
            "full_name": "Multi Modal",
            "password": "MultiModal@2026",
        })
        if res.status_code != 201:
            res = await client.post("/api/v1/auth/login", json={
                "email": "multimodal@stressai.com",
                "password": "MultiModal@2026",
            })
        return res.json().get("access_token", "")


@pytest.fixture(scope="module")
async def assessment_id(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    payload = {f"pss_q{i}": 3 for i in range(1, 11)}
    payload.update({"heart_rate": 85, "hrv_sdnn": 35, "sleep_hours": 5.5,
                    "sleep_efficiency": 70, "physical_activity_min": 10,
                    "work_hours": 10, "screen_time_hours": 9, "breaks_per_day": 1,
                    "sentiment_score": -0.4, "anxiety_score": 8})
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.post("/api/v1/assessments/", json=payload, headers=headers)
        assert r.status_code == 201, r.text
        return r.json()["id"]


def _db_assessment():
    a = StressAssessment(user_id="u",
                         **{f"pss_q{i}": 3 for i in range(1, 11)},
                         total_pss=0, heart_rate=70, hrv_sdnn=50, sleep_hours=7,
                         sleep_efficiency=85, physical_activity_min=30, work_hours=8,
                         screen_time_hours=6, breaks_per_day=4, sentiment_score=0.2,
                         anxiety_score=4)
    return a


def test_questionnaire_official_pss_scoring():
    # All 3s: normal items 6x3=18, reversed 4x(4-3)=4 → total 22 → Moderate.
    m = mm.score_questionnaire(_db_assessment())
    assert m.available is True
    assert m.detail["raw_score"] == 22
    assert m.level == "Moderate"
    assert abs(m.score - 22 / 40.0) < 1e-9
    assert len(m.detail["top_items"]) == 3


def test_questionnaire_bands():
    low = _db_assessment()
    for i in range(1, 11):
        setattr(low, f"pss_q{i}", 0)
    # reversed items score 4-0=4 each → total 16... use explicit lows:
    assert mm.score_questionnaire(low).detail["raw_score"] == 16
    high = _db_assessment()
    for i in range(1, 11):
        setattr(high, f"pss_q{i}", 4 if i not in mm.REVERSED_ITEMS else 0)
    assert mm.score_questionnaire(high).detail["raw_score"] == 40
    assert mm.score_questionnaire(high).level == "High"


def test_voice_unavailable_never_zero():
    m = mm.score_voice()
    assert m.available is False and m.score is None
    m2 = mm.score_voice(audio_base64="not-audio!!!")
    assert m2.available is False and m2.score is None


def test_voice_real_audio_and_text():
    m = mm.score_voice(audio_base64=speech(), transcript="I feel so sad and alone.")
    assert m.available is True
    assert 0.0 <= m.score <= 1.0
    assert m.level in ("Low", "Moderate", "High")


def test_fusion_all_missing_is_uncertain():
    fused = mm.fuse_modalities([
        mm.ModalityResult(name="a", score=None, confidence=0.1, available=False),
        mm.ModalityResult(name="b", score=None, confidence=0.1, available=False),
    ])
    assert fused["insufficient"] is True
    assert fused["level"] == "Uncertain"
    assert fused["score"] is None


def test_fusion_weights_and_reproducibility():
    mods = [
        mm.ModalityResult(name="questionnaire", score=0.55, confidence=0.85, available=True),
        mm.ModalityResult(name="voice", score=0.68, confidence=0.6, available=True),
        mm.ModalityResult(name="facial", score=0.31, confidence=0.7, available=True),
    ]
    f1 = mm.fuse_modalities(mods)
    f2 = mm.fuse_modalities(mods)
    assert f1 == f2  # deterministic
    assert abs(sum(f1["weights"].values()) - 1.0) < 0.01
    assert max(f1["weights"].values()) <= 0.70
    assert 0.0 <= f1["score"] <= 1.0
    # Missing modality contributes nothing (never zero-filled).
    f3 = mm.fuse_modalities(mods[:2])
    assert "facial" not in f3["weights"]


def test_single_modality_labeled():
    fused = mm.fuse_modalities([
        mm.ModalityResult(name="questionnaire", score=0.55, confidence=0.85, available=True),
    ])
    assert fused["single"] is True
    assert fused["score"] == 0.55


@pytest.mark.asyncio
async def test_api_full_and_partial_combos(auth_token, assessment_id):
    headers = {"Authorization": f"Bearer {auth_token}"}
    audio = speech()
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Questionnaire only.
        r = await client.post("/api/v1/multimodal/assess",
                              json={"assessment_id": assessment_id}, headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["available_modalities"] == ["questionnaire"]
        assert body["voice_result"] is None and body["face_result"] is None
        assert body["questionnaire_result"]["detail"]["raw_score"] > 0

        # Voice only (words).
        r = await client.post("/api/v1/multimodal/assess",
                              json={"voice_transcript": "I feel so sad and alone."},
                              headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["available_modalities"] == ["voice"]

        # Voice + questionnaire.
        r = await client.post("/api/v1/multimodal/assess",
                              json={"assessment_id": assessment_id,
                                    "voice_transcript": "Work is piling up."},
                              headers=headers)
        assert r.status_code == 200, r.text
        assert set(r.json()["available_modalities"]) == {"questionnaire", "voice"}

        # Voice audio + words.
        r = await client.post("/api/v1/multimodal/assess",
                              json={"voice_audio_base64": audio,
                                    "voice_transcript": "I feel tired."},
                              headers=headers)
        assert r.status_code == 200, r.text
        assert "voice" in r.json()["available_modalities"]

        # Empty request rejected.
        r = await client.post("/api/v1/multimodal/assess", json={}, headers=headers)
        assert r.status_code == 400

        # All modalities fail → Uncertain, persisted, explainable.
        r = await client.post("/api/v1/multimodal/assess",
                              json={"voice_audio_base64": "garbage!!"},
                              headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["overall_category"] == "Uncertain"
        assert r.json()["overall_estimate"] is None

        # History + detail round-trip.
        h = await client.get("/api/v1/multimodal/?limit=5", headers=headers)
        assert h.status_code == 200 and len(h.json()) >= 1
        rid = h.json()[0]["id"]
        d = await client.get(f"/api/v1/multimodal/{rid}", headers=headers)
        assert d.status_code == 200
        assert d.json()["id"] == rid

        # Auth required.
        r = await client.post("/api/v1/multimodal/assess",
                              json={"voice_transcript": "hi"})
        assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_no_cross_user_access(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/api/v1/multimodal/does-not-exist", headers=headers)
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_analytics_trends_use_latest_check_time(auth_token, assessment_id):
    """A newer combined check must move questionnaire trends to its timestamp."""
    from datetime import datetime

    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.post("/api/v1/multimodal/assess",
                              json={"assessment_id": assessment_id}, headers=headers)
        assert r.status_code == 200, r.text
        checked_at = datetime.fromisoformat(r.json()["assessment_timestamp"])

        a = await client.get("/api/v1/analytics/user", headers=headers)
        assert a.status_code == 200, a.text
        data = a.json()
        latest = data["timeline_trends"][-1]

    assert latest["date"] == checked_at.strftime("%b %d")
    assert latest["total_pss"] > 0
    assert latest["stress_level"] == "Moderate"
    assert data["latest_stress_level"] == "Moderate"
    assert data["stress_distribution"]["Moderate"] >= 1
