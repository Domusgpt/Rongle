"""Integration tests for Portal API — auth flow, devices, subscriptions, quota."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Override settings before importing the app
import os
os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only-32chars!"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_rongle.db"

from portal.app import app
from portal.database import init_db, engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Reset database before each test."""
    await init_db()
    yield
    # Cleanup
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM audit_entries"))
        await conn.execute(text("DELETE FROM usage_records"))
        await conn.execute(text("DELETE FROM devices"))
        await conn.execute(text("DELETE FROM subscriptions"))
        await conn.execute(text("DELETE FROM users"))


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient):
    """Register a user and return auth headers."""
    resp = await client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "testpass123",
        "display_name": "Tester",
    })
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def device_id(client: AsyncClient, auth_headers: dict):
    """Create a device and return its ID."""
    resp = await client.post("/api/devices/", json={
        "name": "Test Device",
        "hardware_type": "android",
    }, headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class TestAuth:
    @pytest.mark.asyncio
    async def test_register(self, client: AsyncClient):
        resp = await client.post("/api/auth/register", json={
            "email": "new@example.com",
            "password": "password123",
            "display_name": "New User",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "otherpass123",
        })
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_login(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token(self, client: AsyncClient):
        # Register to get tokens
        reg = await client.post("/api/auth/register", json={
            "email": "refresh@example.com",
            "password": "password123",
        })
        refresh = reg.json()["refresh_token"]

        resp = await client.post("/api/auth/refresh", json={
            "refresh_token": refresh,
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_protected_endpoint_no_token(self, client: AsyncClient):
        resp = await client.get("/api/users/me")
        assert resp.status_code in (401, 403, 422)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
class TestUsers:
    @pytest.mark.asyncio
    async def test_get_me(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/users/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["display_name"] == "Tester"

    @pytest.mark.asyncio
    async def test_update_display_name(self, client: AsyncClient, auth_headers):
        resp = await client.patch("/api/users/me", json={
            "display_name": "Updated Name",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Updated Name"


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------
class TestDevices:
    @pytest.mark.asyncio
    async def test_create_device(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/devices/", json={
            "name": "My Rongle",
            "hardware_type": "raspberry_pi",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Rongle"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_list_devices(self, client: AsyncClient, auth_headers, device_id):
        resp = await client.get("/api/devices/", headers=auth_headers)
        assert resp.status_code == 200
        devices = resp.json()
        assert len(devices) >= 1

    @pytest.mark.asyncio
    async def test_get_device(self, client: AsyncClient, auth_headers, device_id):
        resp = await client.get(f"/api/devices/{device_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == device_id
        assert "api_key" in data
        assert data["api_key"].startswith("rng_")

    @pytest.mark.asyncio
    async def test_delete_device(self, client: AsyncClient, auth_headers, device_id):
        resp = await client.delete(f"/api/devices/{device_id}", headers=auth_headers)
        assert resp.status_code == 204

        # Verify deleted
        resp2 = await client.get(f"/api/devices/{device_id}", headers=auth_headers)
        assert resp2.status_code == 404

    @pytest.mark.asyncio
    async def test_regenerate_key(self, client: AsyncClient, auth_headers, device_id):
        # Get original key
        resp1 = await client.get(f"/api/devices/{device_id}", headers=auth_headers)
        original_key = resp1.json()["api_key"]

        # Regenerate
        resp2 = await client.post(
            f"/api/devices/{device_id}/regenerate-key", headers=auth_headers
        )
        assert resp2.status_code == 200
        new_key = resp2.json()["api_key"]
        assert new_key != original_key
        assert new_key.startswith("rng_")

    @pytest.mark.asyncio
    async def test_update_settings(self, client: AsyncClient, auth_headers, device_id):
        resp = await client.patch(
            f"/api/devices/{device_id}/settings",
            json={"settings": {"vlm_model": "gemini-2.0-flash"}},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_device_limit_enforcement(self, client: AsyncClient, auth_headers):
        """Free tier allows only 1 device."""
        # First device should succeed
        r1 = await client.post("/api/devices/", json={
            "name": "Device 1", "hardware_type": "android",
        }, headers=auth_headers)
        assert r1.status_code == 201

        # Second device should fail (free tier = 1 device)
        r2 = await client.post("/api/devices/", json={
            "name": "Device 2", "hardware_type": "android",
        }, headers=auth_headers)
        assert r2.status_code in (400, 403)


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------
class TestSubscriptions:
    @pytest.mark.asyncio
    async def test_get_subscription(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/subscription/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "free"
        assert data["llm_quota_monthly"] == 100

    @pytest.mark.asyncio
    async def test_upgrade_tier(self, client: AsyncClient, auth_headers):
        resp = await client.put("/api/subscription/", json={
            "tier": "starter",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "starter"
        assert data["llm_quota_monthly"] == 2000
        assert data["max_devices"] == 3

    @pytest.mark.asyncio
    async def test_usage_endpoint(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/subscription/usage", headers=auth_headers)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------
class TestPolicies:
    @pytest.mark.asyncio
    async def test_get_policy(self, client: AsyncClient, auth_headers, device_id):
        resp = await client.get(
            f"/api/devices/{device_id}/policy", headers=auth_headers
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_set_policy(self, client: AsyncClient, auth_headers, device_id):
        policy = {
            "allowed_regions": [{"x_min": 0, "y_min": 0, "x_max": 1920, "y_max": 1080}],
            "blocked_keystroke_patterns": ["rm -rf"],
        }
        resp = await client.put(
            f"/api/devices/{device_id}/policy",
            json={"policy": policy},
            headers=auth_headers,
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
class TestHealth:
    @pytest.mark.asyncio
    async def test_health(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
