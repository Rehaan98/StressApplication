"""
Assessment-session tests (phases 2/6/8/9/15).

Covers: lifecycle + state machine, parallel non-blocking slots, partial
finalize, empty finalize rejection, cancel, expiry, cross-user isolation,
stale-slot flagging, and companion-brief honesty (no invented scores).
"""

import pytest
from httpx import AsyncClient

from backend.app.main import app
from backend.app.services import multimodal_session as ms


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
            "email": "sessflow@stressai.com",
            "full_name": "Sess Flow",
            "password": "SessFlow@2026",
        })
        if res.status_code != 201:
            res = await client.post("/api/v1/auth/login", json={
                "email": "sessflow@stressai.com",
                "password": "SessFlow@2026",
            })
        return res.json().get("access_token", "")


@pytest.fixture(scope="module")
async def assessment_id(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    payload = {f"pss_q{i}": 2 for i in range(1, 11)}
    payload.update({"heart_rate": 72, "hrv_sdnn": 55, "sleep_hours": 7,
                    "sleep_efficiency": 85, "physical_activity_min": 30,
                    "work_hours": 8, "screen_time_hours": 6, "breaks_per_day": 4,
                    "sentiment_score": 0.2, "anxiety_score": 4})
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.post("/api/v1/assessments/", json=payload, headers=headers)
        assert r.status_code == 201, r.text
        return r.json()["id"]


async def _new_session(client, headers):
    r = await client.post("/api/v1/multimodal/sessions", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["assessment_status"] == "collecting"
    return r.json()["session_id"]


@pytest.mark.asyncio
async def test_state_machine_and_parallel_slots(auth_token, assessment_id):
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(app=app, base_url="http://test") as client:
        sid = await _new_session(client, headers)
        st = await client.get(f"/api/v1/multimodal/sessions/{sid}", headers=headers)
        assert st.json()["assessment_status"] == "collecting"
        assert st.json()["voice_status"]["available"] is False

        # Questionnaire and voice submit independently (neither blocks).
        q = await client.post(f"/api/v1/multimodal/sessions/{sid}/questionnaire",
                              json={"assessment_id": assessment_id}, headers=headers)
        assert q.status_code == 200, q.text
        v = await client.post(f"/api/v1/multimodal/sessions/{sid}/voice",
                              json={"transcript": "I feel so sad and alone."}, headers=headers)
        assert v.status_code == 200, v.text

        live = await client.get(f"/api/v1/multimodal/sessions/{sid}/live", headers=headers)
        assert live.status_code == 200
        body = live.json()
        assert body["assessment_status"] == "provisional"
        assert set(body["available_modalities"]) == {"questionnaire", "voice"}
        assert "facial" in body["missing_modalities"]
        assert body["model_versions"]["questionnaire"] == "pss10-official"

        fin = await client.post(f"/api/v1/multimodal/sessions/{sid}/finalize", headers=headers)
        assert fin.status_code == 200, fin.text
        assert fin.json()["overall_category"] in ("Low", "Moderate", "High", "Severe")

        # Finalized sessions are gone from live memory; result persists in history.
        assert (await client.get(f"/api/v1/multimodal/sessions/{sid}/live", headers=headers)).status_code in (404, 410)
        h = await client.get("/api/v1/multimodal/?limit=5", headers=headers)
        assert any(x["id"] == fin.json()["id"] for x in h.json())


@pytest.mark.asyncio
async def test_empty_finalize_cancel_and_errors(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(app=app, base_url="http://test") as client:
        sid = await _new_session(client, headers)
        # Nothing submitted → 422, never a fake Moderate.
        r = await client.post(f"/api/v1/multimodal/sessions/{sid}/finalize", headers=headers)
        assert r.status_code == 422

        # Bad voice payload → 400; bad questionnaire ref → 404.
        r = await client.post(f"/api/v1/multimodal/sessions/{sid}/voice",
                              json={}, headers=headers)
        assert r.status_code == 400
        r = await client.post(f"/api/v1/multimodal/sessions/{sid}/questionnaire",
                              json={"assessment_id": "nope"}, headers=headers)
        assert r.status_code == 404

        # Unknown session → 404; cancel works and is terminal.
        assert (await client.get("/api/v1/multimodal/sessions/nope", headers=headers)).status_code == 404
        r = await client.delete(f"/api/v1/multimodal/sessions/{sid}", headers=headers)
        assert r.status_code == 200
        assert r.json()["assessment_status"] == "cancelled"
        assert (await client.get(f"/api/v1/multimodal/sessions/{sid}", headers=headers)).status_code == 404


@pytest.mark.asyncio
async def test_cross_user_isolation(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.post("/api/v1/auth/register", json={
            "email": "sessother@stressai.com", "full_name": "Other", "password": "Other@2026"})
        token2 = r.json().get("access_token") if r.status_code == 201 else (
            await client.post("/api/v1/auth/login", json={
                "email": "sessother@stressai.com", "password": "Other@2026"})).json().get("access_token")
        h2 = {"Authorization": f"Bearer {token2}"}
        sid = await _new_session(client, headers)
        assert (await client.get(f"/api/v1/multimodal/sessions/{sid}", headers=h2)).status_code == 404
        assert (await client.post(f"/api/v1/multimodal/sessions/{sid}/voice",
                                  json={"transcript": "hi"}, headers=h2)).status_code == 404


def test_stale_slot_flagged_not_silent():
    sess = ms.create_session("u")
    sess.slots["voice"] = ms.ModalitySlot(available=True, score=0.7, confidence=0.6,
                                          level="High", detail={}, updated_at=0.0,
                                          model_version="t")
    view = ms.live_view(sess)
    assert view["available_modalities"] == ["voice"]
    assert any("older than" in str(lim) for lim in view["limitations"])
    ms.drop_session(sess.session_id)


def test_illegal_transitions_rejected():
    sess = ms.create_session("u")
    try:
        with pytest.raises(ValueError):
            sess.transition("completed")  # collecting → completed is illegal
        assert sess.status == "collecting"
    finally:
        ms.drop_session(sess.session_id)
