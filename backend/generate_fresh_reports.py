import asyncio
import os
from httpx import AsyncClient
from app.main import app
from app.core.workspace import get_workspace_manager
from app.db.client import get_pool
from app.ai.client import get_llm_call_fn
from app.services.orchestrator import run_investigation_loop

async def run():
    print("Generating Fresh Investigation and Workspace Reports...")
    wm = get_workspace_manager()
    
    # 1. Ensure workspace exists
    if not wm.current_workspace:
        await wm.open_workspace("test_fresh2.osint")
        print("Loaded test_fresh2 workspace.")
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM investigations ORDER BY created_at DESC LIMIT 1")
        if not row:
            print("No investigations found!")
            return
        inv_id = str(row["id"])
        print(f"Using investigation {inv_id}")

    # 4. Generate Reports
    print("\nGenerating Reports via API...")
    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Investigation HTML
        print(f"Generating Investigation HTML for {inv_id}...")
        resp = await client.post(f"/api/v1/investigations/{inv_id}/reports", json={"format": "html"})
        print(f"Status: {resp.status_code}, URL: {resp.json().get('download_url')}")
        
        # Workspace HTML
        print("Generating Workspace HTML...")
        resp = await client.post("/api/v1/workspace/reports", json={"format": "html"})
        print(f"Status: {resp.status_code}, URL: {resp.json().get('download_url')}")

    print("\nDone! Please inspect the generated files in backend/reports.")

if __name__ == "__main__":
    asyncio.run(run())
