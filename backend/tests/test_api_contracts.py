"""API contract tests — validate all endpoints return expected schemas.

Task 9.4: Tests that each API endpoint returns the correct status codes,
response shapes, and error handling behavior.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.client import close_pool, reset_pool
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def _reset_db():
    reset_pool()
    yield
    await close_pool()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Health ───────────────────────────────────────────────────────────────────


class TestHealthContract:
    @pytest.mark.anyio
    async def test_health_returns_200(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert data["status"] == "healthy"


# ── Investigations ───────────────────────────────────────────────────────────


class TestInvestigationsContract:
    @pytest.mark.anyio
    async def test_list_investigations_returns_array(self, client: AsyncClient):
        resp = await client.get("/api/v1/investigations")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.anyio
    async def test_create_investigation_missing_name(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/investigations",
            json={"target": "example.com"},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_investigation_missing_target(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/investigations",
            json={"name": "Test"},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_investigation_empty_name(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/investigations",
            json={"name": "", "target": "example.com"},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_get_investigation_not_found(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/investigations/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_stop_investigation_not_found(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/investigations/00000000-0000-0000-0000-000000000000/stop"
        )
        assert resp.status_code in (404, 400)

    @pytest.mark.anyio
    async def test_status_investigation_not_found(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/investigations/00000000-0000-0000-0000-000000000000/status"
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_start_investigation_not_found(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/investigations/00000000-0000-0000-0000-000000000000/start"
        )
        assert resp.status_code == 404


# ── Entities ─────────────────────────────────────────────────────────────────


class TestEntitiesContract:
    @pytest.mark.anyio
    async def test_get_entity_not_found(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/entities/nonexistent",
            params={"investigation_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code in (404, 422)

    @pytest.mark.anyio
    async def test_entity_evidence_not_found(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/entities/nonexistent/evidence",
            params={"investigation_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code in (404, 422)


# ── Graph ────────────────────────────────────────────────────────────────────


class TestGraphContract:
    @pytest.mark.anyio
    async def test_graph_empty_investigation(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/investigations/00000000-0000-0000-0000-000000000000/graph"
        )
        # Graph may return empty or 404 depending on implementation
        assert resp.status_code in (200, 404)


# ── Activity ─────────────────────────────────────────────────────────────────


class TestActivityContract:
    @pytest.mark.anyio
    async def test_activity_not_found(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/investigations/00000000-0000-0000-0000-000000000000/activity"
        )
        assert resp.status_code in (200, 404)

    @pytest.mark.anyio
    async def test_observations_not_found(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/investigations/00000000-0000-0000-0000-000000000000/observations"
        )
        assert resp.status_code in (200, 404)


# ── Reports ──────────────────────────────────────────────────────────────────


class TestReportsContract:
    @pytest.mark.anyio
    async def test_generate_report_not_found(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/investigations/00000000-0000-0000-0000-000000000000/reports",
            json={"format": "html"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_report_not_found(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/investigations/00000000-0000-0000-0000-000000000000/reports/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_reports_empty(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/investigations/00000000-0000-0000-0000-000000000000/reports"
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_generate_report_invalid_format(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/investigations/00000000-0000-0000-0000-000000000000/reports",
            json={"format": "xlsx"},
        )
        # Should be 404 (investigation not found) or 422 (validation error)
        assert resp.status_code in (404, 422)

    @pytest.mark.anyio
    async def test_download_report_not_found(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/investigations/00000000-0000-0000-0000-000000000000/reports/00000000-0000-0000-0000-000000000000/download"
        )
        assert resp.status_code == 404


# ── AI Analysis ──────────────────────────────────────────────────────────────


class TestAIAnalysisContract:
    @pytest.mark.anyio
    async def test_ai_analysis_not_found(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/investigations/00000000-0000-0000-0000-000000000000/ai-analysis"
        )
        assert resp.status_code == 404


# ── Security headers ─────────────────────────────────────────────────────────


class TestSecurityHeaders:
    @pytest.mark.anyio
    async def test_security_headers_present(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
        assert "Referrer-Policy" in resp.headers
