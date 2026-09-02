"""
Backend API Integration Tests — Authentication
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
async def async_client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

async def register_or_login(client: AsyncClient, email: str, full_name: str, password: str):
    """Idempotent registration: registers, or logs in if the user already exists."""
    res = await client.post("/api/v1/auth/register", json={
        "email": email, "full_name": full_name, "password": password
    })
    if res.status_code != 201:
        res = await client.post("/api/v1/auth/login", json={
            "email": email, "password": password
        })
    return res

@pytest.mark.asyncio
async def test_health_check(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "api_version" in data

@pytest.mark.asyncio
async def test_register_user(async_client):
    response = await async_client.post("/api/v1/auth/register", json={
        "email": "testuser_auth@stressai.com",
        "full_name": "Test Auth User",
        "password": "TestPass@2026"
    })
    assert response.status_code in (201, 400)  # 201 fresh, 400 if already registered
    if response.status_code == 201:
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "testuser_auth@stressai.com"

@pytest.mark.asyncio
async def test_register_duplicate_email(async_client):
    # First registration
    await register_or_login(async_client, "duplicate@stressai.com", "Duplicate User", "TestPass@2026")
    # Second registration with same email should fail
    response = await async_client.post("/api/v1/auth/register", json={
        "email": "duplicate@stressai.com",
        "full_name": "Duplicate User 2",
        "password": "TestPass@2026"
    })
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_login_valid_credentials(async_client):
    # Register then login
    await register_or_login(async_client, "logintest@stressai.com", "Login Test User", "LoginPass@2026")
    response = await async_client.post("/api/v1/auth/login", json={
        "email": "logintest@stressai.com",
        "password": "LoginPass@2026"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_invalid_credentials(async_client):
    response = await async_client.post("/api/v1/auth/login", json={
        "email": "notexist@stressai.com",
        "password": "WrongPass123"
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_get_me_with_valid_token(async_client):
    reg = await register_or_login(async_client, "metest@stressai.com", "Me Test User", "MePass@2026")
    token = reg.json()["access_token"]
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "metest@stressai.com"

@pytest.mark.asyncio
async def test_get_me_without_token(async_client):
    response = await async_client.get("/api/v1/auth/me")
    assert response.status_code == 401
