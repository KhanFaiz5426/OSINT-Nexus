"""Tests for investigation API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.client import close_pool, reset_pool
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def _reset_db():
    """Reset the DB pool before each test to avoid stale event loop issues."""
    reset_pool()
    yield
    await close_pool()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthCheck:
    """Test health endpoint."""

    @pytest.mark.anyio
    async def test_health_returns_200(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestCreateInvestigation:
    """Test POST /investigations."""

    @pytest.mark.anyio
    async def test_create_investigation_domain(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/investigations",
            json={"name": "Test Domain", "target": "example.com", "depth": "standard"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Domain"
        assert data["target"] == "example.com"
        assert data["target_type"] == "domain"
        assert data["status"] == "created"
        assert data["depth"] == "standard"
        assert "id" in data

    @pytest.mark.anyio
    async def test_create_investigation_ip(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/investigations",
            json={"name": "Test IP", "target": "8.8.8.8", "depth": "deep"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["target_type"] == "ip"
        assert data["target"] == "8.8.8.8"

    @pytest.mark.anyio
    async def test_create_investigation_url(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/investigations",
            json={"name": "Test URL", "target": "https://example.com/path"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["target_type"] == "url"

    @pytest.mark.anyio
    async def test_create_investigation_email(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/investigations",
            json={"name": "Test Email", "target": "user@example.com"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["target_type"] == "email"
        assert data["target"] == "user@example.com"

    @pytest.mark.anyio
    async def test_create_investigation_username(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/investigations",
            json={"name": "Test Username", "target": "cyberresearcher42"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["target_type"] == "username"

    @pytest.mark.anyio
    async def test_create_investigation_normalizes_domain(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/investigations",
            json={"name": "Normalize Test", "target": "EXAMPLE.COM."},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["target"] == "example.com"

    @pytest.mark.anyio
    async def test_create_investigation_missing_name(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/investigations",
            json={"target": "example.com"},
        )
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_create_investigation_missing_target(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/investigations",
            json={"name": "Test"},
        )
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_create_investigation_empty_name(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/investigations",
            json={"name": "", "target": "example.com"},
        )
        assert response.status_code == 422


class TestListInvestigations:
    """Test GET /investigations."""

    @pytest.mark.anyio
    async def test_list_empty(self, client: AsyncClient):
        response = await client.get("/api/v1/investigations")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.anyio
    async def test_list_includes_created(self, client: AsyncClient):
        # Create one investigation first
        await client.post(
            "/api/v1/investigations",
            json={"name": "List Test", "target": "example.com"},
        )
        response = await client.get("/api/v1/investigations")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    @pytest.mark.anyio
    async def test_list_with_pagination(self, client: AsyncClient):
        response = await client.get("/api/v1/investigations?limit=10&offset=0")
        assert response.status_code == 200


class TestGetInvestigation:
    """Test GET /investigations/{id}."""

    @pytest.mark.anyio
    async def test_get_existing(self, client: AsyncClient):
        # Create first
        create_resp = await client.post(
            "/api/v1/investigations",
            json={"name": "Get Test", "target": "example.com"},
        )
        inv_id = create_resp.json()["id"]

        # Get it
        response = await client.get(f"/api/v1/investigations/{inv_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == inv_id
        assert data["name"] == "Get Test"

    @pytest.mark.anyio
    async def test_get_not_found(self, client: AsyncClient):
        response = await client.get("/api/v1/investigations/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404


class TestStopInvestigation:
    """Test POST /investigations/{id}/stop."""

    @pytest.mark.anyio
    async def test_stop_created_investigation(self, client: AsyncClient):
        # Create first
        create_resp = await client.post(
            "/api/v1/investigations",
            json={"name": "Stop Test", "target": "example.com"},
        )
        inv_id = create_resp.json()["id"]

        # Stop it
        response = await client.post(f"/api/v1/investigations/{inv_id}/stop")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "stopped"

    @pytest.mark.anyio
    async def test_stop_not_found(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/investigations/00000000-0000-0000-0000-000000000000/stop"
        )
        assert response.status_code == 404


class TestGetStatus:
    """Test GET /investigations/{id}/status."""

    @pytest.mark.anyio
    async def test_get_status(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/v1/investigations",
            json={"name": "Status Test", "target": "example.com"},
        )
        inv_id = create_resp.json()["id"]

        response = await client.get(f"/api/v1/investigations/{inv_id}/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "created"
        assert data["id"] == inv_id

    @pytest.mark.anyio
    async def test_get_status_not_found(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/investigations/00000000-0000-0000-0000-000000000000/status"
        )
        assert response.status_code == 404
