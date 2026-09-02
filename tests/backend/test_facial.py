"""
Backend API Integration Tests — Facial Expression Analysis
"""

import base64
import os
import pytest
import asyncio
from httpx import AsyncClient
from backend.app.main import app

TEST_FACE_PATH = "/tmp/lena.jpg"
TEST_FACE_URL = "https://raw.githubusercontent.com/opencv/opencv/4.x/samples/data/lena.jpg"


def _ensure_face_image() -> bool:
    if os.path.exists(TEST_FACE_PATH):
        return True
    try:
        import urllib.request
        urllib.request.urlretrieve(TEST_FACE_URL, TEST_FACE_PATH)
        return os.path.exists(TEST_FACE_PATH)
    except Exception:
        return False


FACE_AVAILABLE = _ensure_face_image()


def _load_face_b64() -> str:
    with open(TEST_FACE_PATH, "rb") as f:
        return base64.b64encode(f.read()).decode()


no_face_image = pytest.mark.skipif(
    not FACE_AVAILABLE,
    reason="No face sample image available (offline environment)."
)


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def auth_token():
    async with AsyncClient(app=app, base_url="http://test") as client:
        res = await client.post("/api/v1/auth/register", json={
            "email": "facial_test@stressai.com",
            "full_name": "Facial Tester",
            "password": "Facial@2026"
        })
        if res.status_code != 201:
            # already registered from previous run — login instead
            res = await client.post("/api/v1/auth/login", json={
                "email": "facial_test@stressai.com",
                "password": "Facial@2026"
            })
        return res.json().get("access_token", "")


@pytest.mark.asyncio
@no_face_image
async def test_analyze_face_image(auth_token):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/facial/analyze",
            json={"image": _load_face_b64(), "source": "webcam"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["face_detected"] is True
    assert data["dominant_emotion"] in {
        "neutral", "happiness", "surprise", "sadness", "anger", "disgust", "fear", "contempt"
    }
    assert 0 <= data["stress_score"] <= 100
    assert data["stress_level"] in {"Low", "Moderate", "High", "Severe"}
    assert data["confidence_score"] > 0


@pytest.mark.asyncio
async def test_analyze_invalid_image(auth_token):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/facial/analyze",
            json={"image": "not-base64!!!", "source": "webcam"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_analyze_empty_image(auth_token):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/facial/analyze",
            json={"image": "", "source": "webcam"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_facial_history(auth_token):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/facial/history",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] >= 1
    assert "current_stress_score" in data


@pytest.mark.asyncio
@no_face_image
async def test_facial_requires_auth():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/facial/analyze",
            json={"image": _load_face_b64(), "source": "webcam"}
        )
    assert response.status_code == 401
