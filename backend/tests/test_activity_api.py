"""Tests for activity log and observations API endpoints (Phase 7)."""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.client import close_pool, get_pool, reset_pool
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


async def _create_investigation(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/investigations",
        json={"name": "Test", "target": "example.com", "depth": "standard"},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _insert_activity(
    investigation_id: str,
    event_type: str,
    details: dict,
) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO activity_log (investigation_id, event_type, details)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            investigation_id,
            event_type,
            json.dumps(details),
        )
    return int(row["id"])


async def _insert_observation(
    investigation_id: str,
    target: str,
    source_adapter: str = "dns",
) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO observations
                (investigation_id, source_adapter, source_version,
                 collected_at, method, target, raw_response,
                 normalized_value, confidence, status)
            VALUES ($1, $2, $3, NOW(), $4, $5, $6, $7, $8, $9)
            RETURNING id::text
            """,
            investigation_id,
            source_adapter,
            "1.0.0",
            "A",
            target,
            json.dumps({"answer": "127.0.0.1"}),
            target,
            0.9,
            "success",
        )
    return row["id"]


class TestActivityEndpoint:
    """Test GET /investigations/{id}/activity."""

    @pytest.mark.anyio
    async def test_activity_not_found(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/investigations/00000000-0000-0000-0000-000000000000/activity"
        )
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_activity_empty(self, client: AsyncClient):
        inv_id = await _create_investigation(client)
        response = await client.get(f"/api/v1/investigations/{inv_id}/activity")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["limit"] == 100
        assert data["offset"] == 0

    @pytest.mark.anyio
    async def test_activity_with_entries(self, client: AsyncClient):
        inv_id = await _create_investigation(client)
        await _insert_activity(inv_id, "investigation_started", {"target": "example.com"})
        await _insert_activity(inv_id, "pivot_round_completed", {"round": 1})

        response = await client.get(f"/api/v1/investigations/{inv_id}/activity")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        types = {item["event_type"] for item in data["items"]}
        assert "investigation_started" in types
        assert "pivot_round_completed" in types

    @pytest.mark.anyio
    async def test_activity_limit_offset(self, client: AsyncClient):
        inv_id = await _create_investigation(client)
        for i in range(5):
            await _insert_activity(inv_id, f"event_{i}", {"i": i})

        response = await client.get(
            f"/api/v1/investigations/{inv_id}/activity",
            params={"limit": 2, "offset": 0},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0

    @pytest.mark.anyio
    async def test_activity_returns_chronological(self, client: AsyncClient):
        inv_id = await _create_investigation(client)
        for i in range(3):
            await _insert_activity(inv_id, f"event_{i}", {"i": i})

        response = await client.get(f"/api/v1/investigations/{inv_id}/activity")
        items = response.json()["items"]
        # Most recent first
        timestamps = [item["created_at"] for item in items]
        assert timestamps == sorted(timestamps, reverse=True)


class TestObservationsEndpoint:
    """Test GET /investigations/{id}/observations."""

    @pytest.mark.anyio
    async def test_observations_not_found(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/investigations/00000000-0000-0000-0000-000000000000/observations"
        )
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_observations_empty(self, client: AsyncClient):
        inv_id = await _create_investigation(client)
        response = await client.get(
            f"/api/v1/investigations/{inv_id}/observations"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_observations_with_entries(self, client: AsyncClient):
        inv_id = await _create_investigation(client)
        obs_id = await _insert_observation(inv_id, "example.com", "dns")

        response = await client.get(
            f"/api/v1/investigations/{inv_id}/observations"
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == obs_id
        assert items[0]["source_adapter"] == "dns"
        assert items[0]["target"] == "example.com"
        assert items[0]["confidence"] == 0.9
        assert items[0]["status"] == "success"
        # raw_response should be a dict, not a JSON string
        assert isinstance(items[0]["raw_response"], dict)
        assert items[0]["raw_response"]["answer"] == "127.0.0.1"

    @pytest.mark.anyio
    async def test_observations_limit_offset(self, client: AsyncClient):
        inv_id = await _create_investigation(client)
        for i in range(5):
            await _insert_observation(inv_id, f"host{i}.com", "dns")

        response = await client.get(
            f"/api/v1/investigations/{inv_id}/observations",
            params={"limit": 3, "offset": 1},
        )
        data = response.json()
        assert len(data["items"]) == 3
        assert data["limit"] == 3
        assert data["offset"] == 1

    @pytest.mark.asyncio
    async def test_observations_pagination_validation(self, client: AsyncClient):
        """Limit and offset should be validated by Query constraints."""
        inv_id = await _create_investigation(client)
        response = await client.get(
            f"/api/v1/investigations/{inv_id}/observations",
            params={"limit": 0},
        )
        assert response.status_code == 422
