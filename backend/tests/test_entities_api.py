import pytest
from httpx import ASGITransport, AsyncClient

from app.db.client import get_pool, close_pool, reset_pool
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

@pytest.mark.anyio
async def test_get_entity_evidence_case_insensitive_fallback(client: AsyncClient):
    """Test that getting entity evidence correctly falls back to case-insensitive matching.
    
    This prevents the '0 evidence' bug where an entity was merged and normalized to
    lowercase (e.g. 'username:jeff geerling'), but its raw observation had a capitalized
    normalized_value ('Jeff Geerling').
    """
    import uuid
    test_investigation_id = str(uuid.uuid4())
    # 1. Insert a raw observation with a capitalized normalized_value
    pool = await get_pool()
    async with pool.acquire() as conn:
        # First ensure investigation exists due to foreign keys
        await conn.execute(
            "INSERT INTO investigations (id, name, target, target_type, status, depth) VALUES ($1, 'Test', 'target', 'domain', 'completed', 'standard')",
            test_investigation_id
        )

        obs_id = await conn.fetchval(
            """
            INSERT INTO observations (
                investigation_id, target, method, 
                source_adapter, source_version, raw_response, 
                normalized_value, confidence, status, collected_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
            RETURNING id
            """,
            test_investigation_id,
            "Jeff Geerling",
            "test_method",
            "github",
            "1.0",
            '{"name": "Jeff Geerling"}',
            "Jeff Geerling",  # Capitalized!
            0.9,
            "success"
        )
        
        # Note: We intentionally do NOT insert an entity_provenance row,
        # to force the fallback logic.

    # 2. Query the evidence endpoint using the lowercase (normalized) entity ID
    response = await client.get(
        f"/api/v1/entities/username:jeff geerling/evidence",
        params={"investigation_id": test_investigation_id}
    )
    
    assert response.status_code == 200
    evidence = response.json()
    
    # 3. Verify the fallback logic matched it via ILIKE
    assert len(evidence) == 1
    assert evidence[0]["id"] == str(obs_id)
    assert evidence[0]["normalized_value"] == "Jeff Geerling"
