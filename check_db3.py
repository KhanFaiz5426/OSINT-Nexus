import sqlite3, glob, json
db_file = glob.glob('backend/test_inv_*.osint')[-1]
conn = sqlite3.connect(db_file)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('SELECT * FROM activity_log WHERE type="investigation_completed"')
rows = cur.fetchall()
for r in rows:
    print("Completed details:", r['details'])
    
cur.execute('SELECT * FROM activity_log WHERE type="ai_recommended_stop"')
rows = cur.fetchall()
for r in rows:
    print("AI Stop details:", r['details'])
    
cur.execute('SELECT id, status, stop_reason FROM investigations LIMIT 1')
inv = cur.fetchone()
print(f"Investigation: status={inv['status']}, stop_reason={inv['stop_reason']}")
