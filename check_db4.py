import sqlite3, glob, json
db_file = glob.glob('backend/test_inv_*.osint')[-1]
conn = sqlite3.connect(db_file)
cur = conn.cursor()
cur.execute('PRAGMA table_info(activity_log)')
print("activity_log columns:", cur.fetchall())

cur.execute('PRAGMA table_info(investigations)')
print("investigations columns:", cur.fetchall())

cur.execute('SELECT * FROM activity_log ORDER BY id DESC LIMIT 5')
rows = cur.fetchall()
print("activity log latest:")
for r in rows:
    print(r)
    
cur.execute('SELECT * FROM investigations LIMIT 1')
print("investigation row:", cur.fetchone())
