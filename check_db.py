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
        row = await conn.fetchrow('SELECT id, status, depth FROM investigations LIMIT 1')
        print(f"DB status: {row['status']}")
        rows = await conn.fetch('SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT 5')
        for r in rows:
            print(f"{r['activity_type']}: {r['details']}")
            
asyncio.run(main())
