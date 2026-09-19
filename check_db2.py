import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath('backend'))
from app.db.client import set_db_path, get_pool

async def main():
    import glob
    db_file = glob.glob('backend/test_inv_*.osint')[-1]
    set_db_path(db_file)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, status, depth FROM investigations LIMIT 1")
        print(f"DB status: {row['status']}")
        
        # let's just get the last activity where type='investigation_completed'
        row2 = await conn.fetchrow("SELECT details FROM activity_log WHERE activity_type='investigation_completed' LIMIT 1")
        if row2:
            import json
            details = json.loads(row2['details'])
            print(f"Completed details: {details}")
            
        row3 = await conn.fetchrow("SELECT details FROM activity_log WHERE activity_type='ai_recommended_stop' LIMIT 1")
        if row3:
            import json
            details = json.loads(row3['details'])
            print(f"AI Stop details: {details}")
            
asyncio.run(main())
