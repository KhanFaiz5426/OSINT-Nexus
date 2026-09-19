import asyncio
import os
import sys
import uuid

# Ensure backend module can be found
sys.path.insert(0, os.path.abspath("backend"))

from app.core.task_manager import get_task_manager
from app.core.workspace import get_workspace_manager
from app.models import TargetType, InvestigationCreate, InvestigationDepth
from app.services.investigation import create_investigation, get_investigation
from app.tasks.run_investigation import run_investigation_async
from app.db.client import close_pool

async def main():
    # Setup test workspace
    random_id = str(uuid.uuid4())
    workspace_path = os.path.abspath(f"backend/test_inv_{random_id}.osint")
        
    wm = get_workspace_manager()
    await wm.create_new(workspace_path)
    
    # Create investigation
    inv_data = InvestigationCreate(
        name="example.com",
        target="example.com",
        target_type=TargetType.DOMAIN,
        depth=InvestigationDepth.SHALLOW
    )
    inv = await create_investigation(inv_data)
    investigation_id = inv.id
    
    print(f"Starting investigation {investigation_id} for example.com...")
    tm = get_task_manager()
    task_info = tm.submit(
        task_id=investigation_id,
        coro=run_investigation_async(investigation_id)
    )
    
    while True:
        inv_status = await get_investigation(investigation_id)
        if inv_status.status.value not in ("pending", "running", "created"):
            break
        print(f"Status: {inv_status.status.value}")
        await asyncio.sleep(2)
        
    print(f"Final Status: {inv_status.status.value}")
    
    # Let's count the graph nodes
    from app.db.neo4j_client import _driver
    if _driver:
        async with _driver.session() as session:
            result = await session.run("MATCH (n) RETURN count(n) as count")
            record = await result.single()
            print(f"Total graph nodes: {record['count']}")
            
    await close_pool()

if __name__ == "__main__":
    asyncio.run(main())
