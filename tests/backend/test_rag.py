"""
Backend API Integration Tests — RAG Coping Interventions
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

@pytest.fixture(scope="module")
async def auth_token():
    async with AsyncClient(app=app, base_url="http://test") as client:
        res = await client.post("/api/v1/auth/register", json={
            "email": "ragtest@stressai.com",
            "full_name": "RAG Tester",
            "password": "RAGTest@2026"
        })
        if res.status_code != 201:
            res = await client.post("/api/v1/auth/login", json={
                "email": "ragtest@stressai.com",
                "password": "RAGTest@2026"
            })
        return res.json().get("access_token", "")

@pytest.mark.asyncio
async def test_rag_query_no_prediction(auth_token):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/rag/",
            json={"query_text": "breathing exercises for high anxiety", "top_k": 3},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    assert response.status_code == 200
    data = response.json()
    assert "interventions" in data
    assert isinstance(data["interventions"], list)
    assert len(data["interventions"]) <= 3

@pytest.mark.asyncio
async def test_rag_query_returns_relevant_results(auth_token):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/rag/",
            json={"query_text": "HRV low sleep poor work stress", "top_k": 3},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    data = response.json()
    assert response.status_code == 200
    # All returned interventions should have required fields
    for item in data["interventions"]:
        assert "id" in item
        assert "title" in item
        assert "category" in item
        assert "protocol" in item
        assert "relevance_score" in item
        assert item["relevance_score"] >= 0.0

@pytest.mark.asyncio
async def test_rag_query_unauthenticated():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/rag/",
            json={"query_text": "stress relief", "top_k": 2}
        )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_rag_query_empty_query(auth_token):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/rag/",
            json={"query_text": "", "top_k": 2},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    # Empty query should still return default interventions (no error)
    assert response.status_code == 200
