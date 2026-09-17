import asyncio
import os
import sys

# Ensure backend path is configured
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.workspace import get_workspace_manager
from app.db.client import get_pool
from app.services.orchestrator import run_investigation_loop
from app.ai.client import get_llm_call_fn

async def run():
    print("Creating a truly fresh workspace and database...")
    wm = get_workspace_manager()
    
    # Force a unique workspace file
    import time
    workspace_name = f"test_fresh_{int(time.time())}.osint"
    await wm.create_new(workspace_name)
    print(f"Created workspace {workspace_name}")
    
    print("Initializing a fresh investigation from scratch...")
    # Target 'geerlingguy' which historically produced the malformed entities
    # We will trigger the orchestrator directly
    try:
        from uuid import uuid4
        # We need an investigation row
        pool = await get_pool()
        async with pool.acquire() as conn:
            inv_id = await conn.fetchval(
                "INSERT INTO investigations (name, target, target_type, status, depth) "
                "VALUES ('Fresh Geerlingguy Test', 'geerlingguy', 'username', 'active', 'standard') RETURNING id"
            )
            print(f"Created investigation {inv_id}")
            
        print("Running deterministic collectors directly to avoid LLM dependency...")
        from app.models.ai import PivotAction
        from app.models import TargetType
        from app.collectors.registry import initialize_collectors
        from app.services.orchestrator import collect_and_store
        await initialize_collectors()
        
        # Trigger DDG search to test domain extraction from text
        await collect_and_store(PivotAction.COLLECT_SEARCH, "geerlingguy", TargetType.USERNAME, str(inv_id))
        
        # We also want to ensure DNS lookup on some domain to test MX records
        # Let's add a second investigation for a domain to ensure MX logic triggers
        async with pool.acquire() as conn:
            domain_inv_id = await conn.fetchval(
                "INSERT INTO investigations (name, target, target_type, status, depth) "
                "VALUES ('Fresh Domain Test', 'messagingengine.com', 'domain', 'active', 'standard') RETURNING id"
            )
            print(f"Created domain investigation {domain_inv_id}")
        await collect_and_store(PivotAction.COLLECT_DNS, "messagingengine.com", TargetType.DOMAIN, str(domain_inv_id))
        
        print("\nVerifying database cleanliness...")
        async with pool.acquire() as conn:
            # Check for bad domains
            bad_domains = await conn.fetch(
                "SELECT value FROM entities WHERE type='domain' AND value LIKE '%ggeerlingguy%'"
            )
            
            # Check for bad MX priorities
            bad_mx = await conn.fetch(
                "SELECT value FROM entities WHERE type='domain' AND value LIKE '%in1-smtp%'"
            )
            
            # Check for generic search strings
            bad_search = await conn.fetch(
                "SELECT value FROM entities WHERE type='domain' AND value LIKE '%Search results for%'"
            )
            
            # All entities for logging
            all_entities = await conn.fetch("SELECT type, value FROM entities LIMIT 100")
            
        print(f"Found {len(bad_domains)} malformed domains (expected 0)")
        for row in bad_domains:
            print(f"  BAD: {row['value']}")
            
        print(f"Found {len(bad_mx)} malformed MX records (expected 0)")
        for row in bad_mx:
            print(f"  MX: {row['value']}")
            
        print(f"Found {len(bad_search)} malformed search results (expected 0)")
        for row in bad_search:
            print(f"  Search: {row['value']}")
            
        print(f"\nTotal entities extracted across both investigations: {len(all_entities)}")
        
        # Generate reports using API
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        
        print("\nGenerating Reports via API...")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            print(f"Generating HTML for {domain_inv_id}...")
            await client.post(f"/api/v1/investigations/{domain_inv_id}/reports", json={"format": "html"})
            
            print("Generating Workspace HTML...")
            await client.post("/api/v1/workspace/reports", json={"format": "html"})
            
        print("\nDone! Fresh investigations completed successfully.")
        
    except Exception as e:
        print(f"Error during fresh investigation: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(run())
