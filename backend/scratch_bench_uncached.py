import time
import re

def _translate_sql_uncached(sql: str) -> str:
    # Translate Postgres $1, $2 to SQLite ?1, ?2 to preserve order.
    sql = re.sub(r'\$(\d+)', r'?\1', sql)
    sql = sql.replace("::text[]", "")
    sql = sql.replace("::uuid[]", "")
    sql = sql.replace("::jsonb", "")
    sql = sql.replace("::text", "")
    sql = sql.replace("::uuid", "")
    sql = sql.replace("ILIKE", "LIKE")
    # Replace ANY(?N) with JSON each for SQLite array simulation
    sql = re.sub(r'=\s*ANY\(\?(\d+)\)', r'IN (SELECT value FROM json_each(?\1))', sql)
    sql = sql.replace("NOW()", "datetime('now', 'utc')")
    return sql

def run_bench():
    queries = [
        "SELECT * FROM users WHERE id = $1 AND name ILIKE $2 AND role = ANY($3::text[])",
        "INSERT INTO investigations (id, name, target, target_type, status) VALUES ($1, $2, $3, $4, $5)",
        "UPDATE observations SET status = $1, updated_at = NOW() WHERE id = $2"
    ]
    
    iterations = 10000
    start = time.perf_counter()
    for _ in range(iterations):
        for q in queries:
            _translate_sql_uncached(q)
            
    elapsed = time.perf_counter() - start
    
    total_calls = iterations * len(queries)
    us_per_call = (elapsed * 1_000_000) / total_calls
    print(f"Uncached - Total time: {elapsed:.3f}s for {total_calls} calls")
    print(f"Uncached - Per call: {us_per_call:.2f} µs")

if __name__ == "__main__":
    run_bench()
