import sqlite3
import os

db_path = os.path.join("app", "data", "osint_nexus_dev.osint")
if os.path.exists(db_path):
    print("Fixing db:", db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE investigations SET status='running' WHERE status='active'")
    conn.commit()
    conn.close()
    print("Done")
else:
    print("DB not found")
