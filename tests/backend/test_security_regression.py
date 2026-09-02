"""
Backend Integration Tests — Security & Regression

Covers:
1. Facial history returns 200 (not 500) for users with zero records
2. User list endpoint requires admin role
3. Admin analytics endpoint requires admin role
4. Prediction detail endpoint (GET /predictions/{id})
5. Profile update + password change endpoints
"""

import pytest
import asyncio
from httpx import AsyncClient
from backend.app.main import app


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


async def _register_or_login(client: AsyncClient, email: str, full_name: str, password: str):
    res = await client.post("/api/v1/auth/register", json={
        "email": email, "full_name": full_name, "password": password
    })
    if res.status_code != 201:
        res = await client.post("/api/v1/auth/login", json={
            "email": email, "password": password
        })
    assert res.status_code in (200, 201), res.text
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_facial_history_empty_user_returns_200():
    """Regression: facial history used to return 500 for users with no records."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        token = await _register_or_login(
            client, "no_facial_records@stressai.com", "No Records Yet", "TestPass@2026"
        )
        response = await client.get(
            "/api/v1/facial/history",
            headers={"Authorization": f"Bearer {token}"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["current_stress_score"] is None
    assert data["current_stress_level"] is None


@pytest.mark.asyncio
async def test_users_list_requires_admin():
    """Regression: any authenticated user could list all users with emails."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        token = await _register_or_login(
            client, "regular_user_ml@stressai.com", "Regular User", "TestPass@2026"
        )
        response = await client.get(
            "/api/v1/users/",
            headers={"Authorization": f"Bearer {token}"}
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_analytics_requires_admin():
    """Regression: system-wide analytics leaked to any authenticated user."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        token = await _register_or_login(
            client, "regular_user_ml2@stressai.com", "Regular User 2", "TestPass@2026"
        )
        response = await client.get(
            "/api/v1/analytics/admin",
            headers={"Authorization": f"Bearer {token}"}
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_prediction_detail_endpoint():
    """GET /predictions/{id} returns prediction with XAI + RAG payloads."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        token = await _register_or_login(
            client, "pred_detail@stressai.com", "Prediction Detail", "TestPass@2026"
        )
        headers = {"Authorization": f"Bearer {token}"}

        assessment = await client.post("/api/v1/assessments/", json={
            "pss_q1": 3, "pss_q2": 3, "pss_q3": 3, "pss_q4": 1, "pss_q5": 1,
            "pss_q6": 3, "pss_q7": 1, "pss_q8": 2, "pss_q9": 3, "pss_q10": 3,
            "heart_rate": 82.0, "hrv_sdnn": 44.0, "sleep_hours": 6.0,
            "sleep_efficiency": 78.0, "physical_activity_min": 20.0,
            "work_hours": 10.0, "screen_time_hours": 7.5, "breaks_per_day": 2,
            "sentiment_score": -0.1, "anxiety_score": 6.5,
        }, headers=headers)
        assert assessment.status_code == 201, assessment.text
        assessment_id = assessment.json()["id"]

        prediction = await client.post("/api/v1/predictions/", json={
            "assessment_id": assessment_id
        }, headers=headers)
        assert prediction.status_code == 201, prediction.text
        prediction_data = prediction.json()
        assert "Severe" in prediction_data["class_probabilities"] or \
               "High" in prediction_data["class_probabilities"]

        detail = await client.get(
            f"/api/v1/predictions/{prediction_data['id']}",
            headers=headers
        )
        assert detail.status_code == 200, detail.text
        data = detail.json()
        assert data["id"] == prediction_data["id"]
        assert data["stress_level"] == prediction_data["stress_level"]
        assert data["confidence_score"] == prediction_data["confidence_score"]
        assert data["shap_explanation"] is not None


@pytest.mark.asyncio
async def test_update_profile_and_password():
    async with AsyncClient(app=app, base_url="http://test") as client:
        token = await _register_or_login(
            client, "settings_user@stressai.com", "Settings User", "TestPass@2026"
        )
        headers = {"Authorization": f"Bearer {token}"}

        update = await client.put("/api/v1/users/me", json={
            "full_name": "Updated Name"
        }, headers=headers)
        assert update.status_code == 200, update.text
        assert update.json()["full_name"] == "Updated Name"

        pwd = await client.post("/api/v1/users/me/password", json={
            "current_password": "TestPass@2026",
            "new_password": "NewPass@2026"
        }, headers=headers)
        assert pwd.status_code == 204, pwd.text

        login = await client.post("/api/v1/auth/login", json={
            "email": "settings_user@stressai.com",
            "password": "NewPass@2026"
        })
        assert login.status_code == 200

        bad_pwd = await client.post("/api/v1/users/me/password", json={
            "current_password": "WrongPass@2026",
            "new_password": "AnotherPass@2026"
        }, headers=headers)
        assert bad_pwd.status_code == 400