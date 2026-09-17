import time
from app.db.client import AsyncpgCompatibleConnection

def run_bench():
    queries = [
        "SELECT * FROM users WHERE id = $1 AND name ILIKE $2 AND role = ANY($3::text[])",
        "INSERT INTO investigations (id, name, target, target_type, status) VALUES ($1, $2, $3, $4, $5)",
        "UPDATE observations SET status = $1, updated_at = NOW() WHERE id = $2"
    ]
    
    # Warm up cache
    for q in queries:
        AsyncpgCompatibleConnection._translate_sql(q)
        
    iterations = 10000
    start = time.perf_counter()
    for _ in range(iterations):
        for q in queries:
            AsyncpgCompatibleConnection._translate_sql(q)
            
    elapsed = time.perf_counter() - start
    
    total_calls = iterations * len(queries)
    us_per_call = (elapsed * 1_000_000) / total_calls
    print(f"Total time: {elapsed:.3f}s for {total_calls} calls")
    print(f"Per call: {us_per_call:.2f} µs")

if __name__ == "__main__":
    run_bench()
