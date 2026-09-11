import os

file_path = "DESKTOP_MIGRATION_SPEC.md"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Update 7.2
old_7_2 = """### 7.2 Graph Query Scalability
- **Test Set:** 10k nodes / 30k edges, and 50k nodes / representative larger edge set.
- **1-hop Neighbor Lookup:** < 50ms (p99). Important for responsive node expansion.
- **Bounded 4-Hop Traversal:** < 500ms (p95). Important for AI planning context.
- **Memory Usage:** The database query must not cause massive memory spikes in the Python process.
- **Correctness:** Must properly prevent infinite loops in cyclic graphs."""

new_7_2 = """### 7.2 Graph Query Scalability
- **Test Set:** 10k nodes / 30k edges, and 50k nodes / representative larger edge set.
- **Queries to Benchmark:**
  - 1-hop neighbor lookup
  - Bounded 2-hop traversal
  - Bounded 4-hop traversal
  - Subgraph extraction
  - Filtered traversal (e.g., specific entity type)
  - Cyclic graph traversal
  - High-branching graph traversal
  - Repeated queries (cache behavior)
  - Graph updates while querying (WAL contention)
- **Metrics (measured across workloads):** p50, p95, p99, worst-case query time, memory consumption, and database size.
- **Target Thresholds:** 1-hop neighbor < 50ms (p99) for UI responsiveness; Bounded 4-Hop < 500ms (p95) for AI planning.
- **Correctness:** Must properly prevent infinite loops in cyclic graphs using path-tracking in the CTE.
- **Indexes:** Ensure appropriate indexes exist on `source_id`, `target_id`, `relationship_type`, and investigation identifiers."""

content = content.replace(old_7_2, new_7_2)

# Update ADR 7
old_adr_7 = """### ADR 7: Search Architecture (SearXNG Removal)
- **Current:** Local SearXNG container via Docker.
- **Candidate Replacement:** `SearchProvider` abstraction supporting multiple backends.
- **Required Behavior:** Provide web search capabilities without requiring local Docker or a complex local Python installation of SearXNG.
- **Status:** **Approved.**
- **Rationale:** The application must satisfy the requirement that search works immediately after installation. We will define an abstract `SearchProvider` interface. The application will use a built-in DuckDuckGo HTML scraper as the default fallback for zero-configuration searches. However, acknowledging the fragility and rate-limiting of HTML scraping, the application will provide first-class support for users to configure reliable API keys (Brave Search, Tavily, Serper.dev) in the Windows Credential Manager."""

new_adr_7 = """### ADR 7: Search Architecture (SearXNG Removal)
- **Current:** Local SearXNG container via Docker.
- **Candidate Replacement:** `SearchProvider` abstraction supporting multiple backends.
- **Required Behavior:** Provide web search capabilities without requiring local Docker or a complex local Python installation of SearXNG.
- **Status:** **Approved.**
- **Rationale:** The application must satisfy the requirement that search works immediately after installation without Docker. We will define an abstract `SearchProvider` interface.
  - **Default/Fallback Provider:** A built-in DuckDuckGo HTML scraper provides zero-configuration searches. 
  - **API Providers:** First-class support for Brave Search, Tavily, and Serper.dev via API keys configured in the Windows Credential Manager.
  - **Provider Selection & Failover:** The orchestrator will attempt to use configured API providers first. If they fail (timeout, rate limit) or no API key exists, it will fall back to the DuckDuckGo scraper. If the scraper is rate-limited or broken, the collector fails gracefully with a timeout/error status.
  - **Reliability:** Acknowledge that HTML scraping is fragile; the UI should explicitly recommend configuring API keys for robust collection. Retries and rate limits (via `aiolimiter`) will be strictly applied to all search requests."""

content = content.replace(old_adr_7, new_adr_7)

# Update ADR 3 Task Lifecycle
old_adr_3 = """  - **Lifecycle:** The manager must support graceful cancellation of tasks when the application shuts down or the user closes the `.osint` file. CPU-bound operations (e.g., massive JSON parsing) must be explicitly delegated to `asyncio.to_thread()` or `ProcessPoolExecutor` to avoid blocking the event loop."""

new_adr_3 = """  - **Lifecycle & Cancellation:** The manager must support graceful cancellation, pause (if applicable), and timeout of tasks when the application shuts down or the user closes the `.osint` file. If the application crashes, in-memory task states are lost, but upon reopening the `.osint` file, the orchestrator resumes based on the durable investigation state (completed observations).
  - **Isolation:** Collector failures must be isolated and reported without crashing the event loop or other tasks.
  - **CPU-bound Delegation:** CPU-bound operations (e.g., massive JSON parsing, cryptography) must be explicitly delegated to `asyncio.to_thread()` or a `ProcessPoolExecutor` to avoid blocking the event loop."""

content = content.replace(old_adr_3, new_adr_3)

# Update 7.1 SQLite Benchmark Workload
old_7_1 = """### 7.1 Storage Scalability (SQLite Workload)
Simulate approximately 10 concurrent I/O-bound collectors producing observations, entities, relationships, and activity logs, while a simulated UI simultaneously queries neighbors, counts, and graph data.
- **Load/Open Time:** SQLite database connection and schema verification < 1.0 seconds.
- **Write Latency:** p95 write latency < 50ms, p99 < 150ms. (Predictable contention ensures UI remains responsive).
- **Read Latency:** UI queries must complete in < 50ms (p95) while writes are occurring, proving WAL isolation is effective.
- **Database Locks:** The application must successfully complete the workload with zero unhandled `database is locked` errors (relying on `busy_timeout` or write queues).
- **Event-Loop Lag:** JSON deserialization must not cause event loop lag exceeding 50ms per tick (vital for UI API responsiveness).
- **WAL Size:** The WAL file must not grow unbounded during heavy collection rounds."""

new_7_1 = """### 7.1 Storage Scalability (SQLite Workload)
Simulate approximately 10 concurrent I/O-bound collectors producing observations, entity creation, relationship creation, and activity-log writes, while a simulated UI simultaneously issues concurrent neighbor, count, and entity queries.
- **Metrics to Measure:** Successful transaction count, write throughput, transaction duration, database-lock errors, and retry count.
- **Load/Open Time:** SQLite database connection and schema verification < 1.0 seconds.
- **Write Latency:** p50 < 10ms, p95 < 50ms, p99 < 150ms. (Predictable contention ensures UI remains responsive).
- **Read Latency:** UI queries must complete in < 50ms (p95) while writes are occurring, proving WAL isolation is effective.
- **Database Locks:** The application must successfully complete the workload with zero unhandled `database is locked` errors (relying on `busy_timeout` or write queues). Bounded contention is acceptable; lock failures are not.
- **Event-Loop Lag:** Must not exceed 50ms per tick (vital for UI API responsiveness).
- **WAL Size:** The WAL file must not grow unbounded during heavy collection rounds."""

content = content.replace(old_7_1, new_7_1)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Details updated.")
