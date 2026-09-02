"""
Backend API Integration Tests — Stress Assessments
"""

import pytest
import asyncio
from httpx import AsyncClient
from backend.app.main import app

SAMPLE_ASSESSMENT = {
    "pss_q1": 3, "pss_q2": 3, "pss_q3": 2,
    "pss_q4": 1, "pss_q5": 1, "pss_q6": 3,
    "pss_q7": 1, "pss_q8": 2, "pss_q9": 3, "pss_q10": 3,
    "heart_rate": 82.0, "hrv_sdnn": 44.0, "sleep_hours": 6.0,
    "sleep_efficiency": 78.0, "physical_activity_min": 20.0,
    "work_hours": 10.0, "screen_time_hours": 7.5,
    "breaks_per_day": 2, "sentiment_score": -0.1, "anxiety_score": 6.5
}

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="module")
async def auth_token():
    async with AsyncClient(app=app, base_url="http://test") as client:
        res = await client.post("/api/v1/auth/register", json={
            "email": "assess_test@stressai.com",
            "full_name": "Assessment Tester",
            "password": "AssTest@2026"
        })
        if res.status_code != 201:
            res = await client.post("/api/v1/auth/login", json={
                "email": "assess_test@stressai.com",
                "password": "AssTest@2026"
            })
        return res.json().get("access_token", "")

@pytest.mark.asyncio
async def test_create_assessment(auth_token):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/assessments/",
            json=SAMPLE_ASSESSMENT,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["total_pss"] is not None
    assert data["heart_rate"] == 82.0

@pytest.mark.asyncio
async def test_list_assessments(auth_token):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/assessments/",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_create_assessment_unauthenticated():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/assessments/", json=SAMPLE_ASSESSMENT)
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_create_assessment_invalid_pss_value(auth_token):
    bad_data = SAMPLE_ASSESSMENT.copy()
    bad_data["pss_q1"] = 9  # Out of valid range 0-4
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/assessments/",
            json=bad_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    assert response.status_code == 422  # Validation error

@pytest.mark.asyncio
async def test_total_pss_calculated_correctly(auth_token):
    """PSS-10 reverse scoring: items 4,5,7,8 are reversed. Total should be computed server-side."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/assessments/",
            json=SAMPLE_ASSESSMENT,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    data = response.json()
    # Manual calculation: normal items (q1,q2,q3,q6,q9,q10) + reversed (q4,q5,q7,q8)
    normal = SAMPLE_ASSESSMENT["pss_q1"] + SAMPLE_ASSESSMENT["pss_q2"] + SAMPLE_ASSESSMENT["pss_q3"] + \
             SAMPLE_ASSESSMENT["pss_q6"] + SAMPLE_ASSESSMENT["pss_q9"] + SAMPLE_ASSESSMENT["pss_q10"]
    reversed_sum = sum(4 - SAMPLE_ASSESSMENT[f"pss_q{q}"] for q in [4, 5, 7, 8])
    expected_total = normal + reversed_sum
    assert data["total_pss"] == expected_total

@pytest.mark.asyncio
async def test_partial_assessment_accepted(auth_token):
    """Users may skip questions — missing PSS items are filled with neutral defaults (2)."""
    partial = {
        # Only answer 4 of 10 PSS items
        "pss_q1": 3,
        "pss_q2": 4,
        "pss_q5": 1,
        "pss_q9": 2,
        # No physiological/workload fields at all
    }
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/assessments/",
            json=partial,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    assert response.status_code == 201
    data = response.json()
    # Answered items preserved
    assert data["pss_q1"] == 3
    assert data["pss_q2"] == 4
    # Skipped items defaulted to neutral 2
    assert data["pss_q3"] == 2
    assert data["pss_q6"] == 2
    assert data["pss_q10"] == 2
    # total_pss computed with defaults: normal(q1,q2,q3,q6,q9,q10) + reversed(q4,q5,q7,q8)
    normal = 3 + 4 + 2 + 2 + 2 + 2
    reversed_sum = (4 - 2) + (4 - 1) + (4 - 2) + (4 - 2)
    assert data["total_pss"] == normal + reversed_sum
    # Physiological defaults applied so ML can run
    assert data["heart_rate"] == 72.0
    assert data["sleep_hours"] == 7.0

@pytest.mark.asyncio
async def test_blank_assessment_accepted(auth_token):
    """Even a fully blank assessment is accepted (all-neutral)."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/assessments/",
            json={},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    assert response.status_code == 201
    data = response.json()
    assert data["total_pss"] == 20  # 10 items × neutral 2
    assert data["anxiety_score"] == 4.0
