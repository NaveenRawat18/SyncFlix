"""
Basic integration tests for SyncFlix API.
Run: pytest tests/ -v
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def client():
    from app.database import init_db
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_register_and_login(client):
    # Register
    r = await client.post("/api/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123",
    })
    assert r.status_code == 201
    data = r.json()
    assert "access_token" in data
    token = data["access_token"]

    # Login
    r2 = await client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "password123",
    })
    assert r2.status_code == 200
    assert "access_token" in r2.json()

    return token


@pytest.mark.asyncio
async def test_rooms_crud(client):
    # Register to get token
    r = await client.post("/api/auth/register", json={
        "username": "hostuser",
        "email": "host@example.com",
        "password": "password123",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create room
    r2 = await client.post("/api/rooms", json={
        "title": "Test Room",
        "description": "A test room",
        "video_url": "https://example.com/video.mp4",
        "category": "Movies",
    }, headers=headers)
    assert r2.status_code == 201
    room_id = r2.json()["id"]

    # Get room
    r3 = await client.get(f"/api/rooms/{room_id}")
    assert r3.status_code == 200
    assert r3.json()["title"] == "Test Room"

    # List rooms
    r4 = await client.get("/api/rooms")
    assert r4.status_code == 200
    assert isinstance(r4.json(), list)

    # Update room
    r5 = await client.patch(f"/api/rooms/{room_id}", json={"status": "live"}, headers=headers)
    assert r5.status_code == 200
    assert r5.json()["status"] == "live"

    # Delete room
    r6 = await client.delete(f"/api/rooms/{room_id}", headers=headers)
    assert r6.status_code == 204
