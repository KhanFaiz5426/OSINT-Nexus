import asyncio
import os
import httpx
from datetime import datetime

API_BASE = "http://127.0.0.1:62122/api/v1"

async def run():
    import sys
    sys.path.append(".")
    from app.core.workspace import WorkspaceManager
    from app.db.client import get_pool
    from app.services.orchestrator import run_investigation_loop
    from app.ai.client import get_llm_call_fn
    import uuid

    wm = WorkspaceManager()
    ws_name = f"test_fresh_{int(datetime.now().timestamp())}.osint"
    await wm.create_new(ws_name)
    print(f"Created workspace: {ws_name}")

    inv_id = str(uuid.uuid4())
    target = "example.com"
    target_type = "domain"

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO investigations (id, name, target, target_type, status, depth)
            VALUES ($1, $2, $3, $4, 'running', 'standard')
        """, inv_id, "Fresh Final Verification", target, target_type)
    
    print(f"Running Orchestrator for {inv_id}...")
    await run_investigation_loop(inv_id, llm_call_fn=get_llm_call_fn())
    
    await wm.close_workspace()
    
    print(f"\nInvestigation complete! Requesting packaged app to open {ws_name}...")
    
    async with httpx.AsyncClient(base_url=API_BASE, timeout=60.0) as client:
        resp = await client.post("/workspace/open", json={"path": os.path.abspath(ws_name)})
        print("Open workspace:", resp.status_code, resp.json())
        
        print("Generating Investigation HTML...")
        resp = await client.post(f"/investigations/{inv_id}/reports", json={"format": "html"})
        print(resp.status_code, resp.json())
        
        print("Generating Workspace HTML...")
        resp = await client.post("/workspace/reports", json={"format": "html"})
        print(resp.status_code, resp.json())

if __name__ == "__main__":
    asyncio.run(run())
