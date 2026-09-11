import os

content = """# OSINT Nexus: Desktop Migration Specification

**Version:** 3.1 (Final Architecture Refinement)
**Date:** 2026-09-11
**Document Type:** Technical Migration Specification

---

## 1. Executive Summary

OSINT Nexus is transitioning from a distributed containerized web service (Docker, PostgreSQL, Neo4j, Celery, Redis) into a standalone, locally executing desktop application. The application will retain its automated OSINT pipeline, AI-assisted investigation planning, and workstation-style UI, requiring zero infrastructure management from the end user.

The target experience is a double-click executable (`osint-nexus.exe` / `osint-nexus.app`) that opens directly into a native window, allowing the user to create or open portable `.osint` investigation files.

---

## 2. Product Goals & Non-Goals

### 2.1 Product Goals
- Zero-configuration launch (no Docker, no manual database setup, no manual browser navigation).
- Portable investigation state via `.osint` files (save, share, continue later).
- Complete preservation of the existing OSINT correlation engine, data models, and AI planner.
- Native desktop window experience.
- Passive/public OSINT workflow only.

### 2.2 Non-Goals (Explicitly Out of Scope)
- Modifying or redesigning the existing React/Cytoscape UI workstation.
- Multi-user collaboration, RBAC, or team syncing.
- Authentication mechanisms for the local app.
- Cloud hosting capabilities or browser-based remote access.
- Active exploitation, vulnerability scanning, or non-OSINT features (e.g., Maltego clone).
- Distributed task scaling across multiple machines.

---

## 3. Current Architecture & Implementation Dependency Map

The repository implements a rigid Collect → Normalize → Extract → Resolve → Correlate pipeline.

### 3.1 Subsystem Mapping
- **Frontend Layer:** React SPA (Vite, Cytoscape.js, TanStack query).
- **API Layer:** FastAPI (`backend/app/main.py`). Defines endpoints in `backend/app/api/` via dependency injection.
- **Investigation Lifecycle:** Managed deterministically by `backend/app/services/orchestrator.py` (`run_investigation_loop`).
- **Relational Storage:** PostgreSQL via raw `asyncpg` queries (`backend/app/db/`). Stores investigations, JSONB observations, and activity logs.
- **Graph Storage:** Neo4j via Cypher queries (`backend/app/graph/`). Stores extracted entities and relationships. Used for bounded BFS paths and neighbor retrieval.
- **Background Execution:** Celery + Redis (`backend/app/tasks/run_investigation.py`). Wraps the async orchestrator loop.
- **Caching & Rate Limiting:** Redis-backed (`backend/app/core/redis.py`), utilized by the OSINT collector adapters.
- **Configuration:** Handled via `.env` and `backend/app/core/settings_store.py`.

---

## 4. Target Desktop Architecture

- **Frontend:** React SPA built with Vite (compiled to static files).
- **Desktop Shell:** Technology-neutral container (`pywebview` wrapping the FastAPI instance and React build into a single native window).
- **Storage:** A single `.osint` file (embedded SQLite database) per investigation containing both document data and graph edges.
- **Graph Engine:** Raw SQLite recursive queries (`WITH RECURSIVE`) replacing Neo4j.
- **Task Queue:** Local execution pool (Python `asyncio`) running within the same process.
- **Cache/Rate Limiting:** In-memory Python caching (`cachetools`) and token-bucket limiters.
- **Deployment:** Single packaged executable (`onedir`) via PyInstaller, wrapped in a Windows Installer.

---

## 5. Investigation File Specification (`.osint`)

The `.osint` file is a robust, portable data format representing the entire state of an investigation. It is implemented as a **SQLite 3 database**.

### 5.1 Internal Schema & Entities
- `metadata`: Tracks `schema_version`, investigation name, target, target_type, status, depth, budget utilized, created/updated timestamps.
- `observations`: Immutable evidence records containing raw source JSON, normalization results, confidence scores, and timestamps.
- `entities`: Extracted intelligence nodes (id, type, value, properties).
- `relationships`: Discovered graph edges (source_id, target_id, type, confidence, evidence_ids).
- `activity_log`: Audit trail of the orchestration loop, AI recommendations, and manual user actions.
- `notes`: Analyst scratchpad and hypotheses.

### 5.2 Lifecycle Behavior
- **Save/Atomic Save:** Because it is a live SQLite database, saves are continuous via transactions. "Save As" is accomplished via the authoritative SQLite Online Backup API during a safe state. Do not simply copy a live WAL-mode database as a static file.
- **Open/Close:** Opening a file binds the FastAPI dependency pool to that specific file. Closing it releases locks and connection pools.
- **Corruption/Recovery:** Before opening an existing `.osint` file, the app must create an automatic `.bak` backup copy. WAL (Write-Ahead Logging) is used as part of the concurrency and durability strategy. If forced process termination occurs, SQLite will recover from the WAL on the next open.
- **File Locking:** Standard SQLite file locking mechanisms apply. If the file is locked by another process (e.g., opened twice), the app must gracefully deny access.

### 5.3 Versioning & Migrations
- `schema_version` is tracked strictly via SQLite `PRAGMA user_version`. 
- Opening an older `.osint` file automatically triggers sequential migration scripts before allowing read/write access.
- Future compatibility is guaranteed by strict schema immutability for older versions.

### 5.4 Configuration & Secrets (CRITICAL)
- The `.osint` file must **NEVER** contain API keys, LLM tokens, or local path secrets.
- Non-secret application configuration (theme, default search providers) is stored in a Windows-aware path: `%APPDATA%\\osint-nexus\\config.json`.
- Sensitive secrets (API keys, LLM tokens) must be stored securely using the **Windows Credential Manager** (via `keyring` or similar native library).

### 5.5 SQLite Connection Architecture
The SQLite layer is fundamentally different from a PostgreSQL connection pool. The architecture is defined as follows:
- **Concurrency Model:** SQLite allows concurrent readers but only **one single writer**.
- **WAL Mode:** `PRAGMA journal_mode=WAL` is enforced to allow readers (UI) to proceed without blocking the writer (collectors).
- **Connection Lifecycle:** When a `.osint` file is opened, the connection manager establishes a small fixed number of connections.
- **Write Serialization:** All writes must be serialized. `PRAGMA busy_timeout=5000` is enforced so that concurrent write attempts wait gracefully for the lock rather than immediately failing with "database is locked". If necessary, a dedicated background writer queue/thread will serialize writes.
- **Transaction Boundaries:** Transactions must be short-lived. Long-running collectors must not hold an active write transaction while waiting for network I/O.

---

## 6. Security Architecture

### 6.1 Authentication (Intentionally Out of Scope)
Authentication (JWT/RBAC) is **explicitly removed and intentionally out of scope** for the standalone local product. The application runs on the user's local machine, under their OS user context, binding only to local interfaces. 

### 6.2 Application Security Areas
- **API Bindings:** Local API endpoints must bind strictly to `127.0.0.1` and reject cross-origin requests from non-local domains to prevent drive-by localhost attacks.
- **SSRF Protection:** The existing `security.py` preventing internal network scanning remains strictly enforced. Malicious `.osint` targets cannot be used to map the user's LAN.
- **Untrusted .osint File Safe-Open:** To safely handle investigation files from untrusted sources, opening a database must:
  - Disable loading of SQLite external extensions (`enable_load_extension(False)`).
  - Enforce `PRAGMA trusted_schema = OFF` to prevent malicious trigger/view execution.
  - Perform strict schema and migration validation before issuing standard application queries.
  - Enforce bounded limits on JSON payload sizes to prevent resource exhaustion attacks.
- **Path Traversal:** File open/save APIs must strictly validate paths against traversal payloads.

---

## 7. Scalability Requirements

Scalability verification is broken down across physical and logical domains. 
Benchmarks must represent realistic OSINT workloads.

### 7.1 Storage Scalability (SQLite Workload)
Simulate approximately 10 concurrent I/O-bound collectors producing observations, entities, relationships, and activity logs, while a simulated UI simultaneously queries neighbors, counts, and graph data.
- **Load/Open Time:** SQLite database connection and schema verification < 1.0 seconds.
- **Write Latency:** p95 write latency < 50ms, p99 < 150ms. (Predictable contention ensures UI remains responsive).
- **Read Latency:** UI queries must complete in < 50ms (p95) while writes are occurring, proving WAL isolation is effective.
- **Database Locks:** The application must successfully complete the workload with zero unhandled `database is locked` errors (relying on `busy_timeout` or write queues).
- **Event-Loop Lag:** JSON deserialization must not cause event loop lag exceeding 50ms per tick (vital for UI API responsiveness).
- **WAL Size:** The WAL file must not grow unbounded during heavy collection rounds.

### 7.2 Graph Query Scalability
- **Test Set:** 10k nodes / 30k edges, and 50k nodes / representative larger edge set.
- **1-hop Neighbor Lookup:** < 50ms (p99). Important for responsive node expansion.
- **Bounded 4-Hop Traversal:** < 500ms (p95). Important for AI planning context.
- **Memory Usage:** The database query must not cause massive memory spikes in the Python process.
- **Correctness:** Must properly prevent infinite loops in cyclic graphs.

### 7.3 Visualization & UI Scalability
- **Render Time:** Cytoscape rendering up to 2,000 nodes without noticeable UI freezing (< 1.5 seconds).
- **Pagination:** If graph exceeds 2,000 nodes, the UI must gracefully paginate or aggressively cluster nodes by default.

---

## 8. Architectural Decision Records (ADRs)

### ADR 1: Storage Layer
- **Current:** PostgreSQL 16+ via `asyncpg`.
- **Candidate Replacement:** SQLite via `aiosqlite`.
- **Required Behavior:** JSON querying, transactional integrity, concurrent read access.
- **Status:** **Proposed / Requires Benchmark.**
- **Benchmark Acceptance Criteria:** Prove the realistic OSINT workload defined in 7.1 completes within defined p95/p99 latency thresholds with zero lock-contention errors.

### ADR 2: Graph Engine
- **Current:** Neo4j via AsyncDriver.
- **Candidate Replacement:** Raw SQLite Recursive CTEs (`WITH RECURSIVE`), executed via `aiosqlite`.
- **Required Behavior:** 4-hop bounded pathfinding, subgraph extraction, neighbor queries.
- **Status:** **Proposed / Requires Benchmark.**
- **Rationale:** SQLite officially supports recursive CTE graph traversal, but actual performance depends on graph topology, branching factor, indexes, depth, and cycles. 
- **Benchmark Acceptance Criteria:** Pass the Graph Query Scalability targets (7.2), proving SQLite can handle required graph shapes (cyclic, high-branching) safely with appropriate cycle-prevention logic and indexing on `source_id`/`target_id`.

### ADR 3: Background Workers & Execution
- **Current:** Celery + Redis.
- **Candidate Replacement:** Native `asyncio` task pool manager.
- **Required Behavior:** Concurrent API collection, timeout enforcement, rate-limiting, failure recovery.
- **Status:** **Proposed / Requires PoC.**
- **Rationale:** `asyncio.create_task()` alone is not a task system. The implementation must define a complete task lifecycle manager tracking task IDs, states (running, completed, failed, cancelled), timeouts, and retries.
  - **State Segregation:** In-memory execution state (task status) is distinct from durable investigation state (observations in SQLite).
  - **Lifecycle:** The manager must support graceful cancellation of tasks when the application shuts down or the user closes the `.osint` file. CPU-bound operations (e.g., massive JSON parsing) must be explicitly delegated to `asyncio.to_thread()` or `ProcessPoolExecutor` to avoid blocking the event loop.

### ADR 4: Caching & Rate Limiting
- **Current:** Redis.
- **Candidate Replacement:** `cachetools.TTLCache` (in-memory) + `aiolimiter`.
- **Required Behavior:** Prevent OSINT API bans via strict token buckets; cache repeated queries for 24h.
- **Status:** **Approved.**

### ADR 5: Desktop Shell Integration
- **Current:** N/A (Web Browser).
- **Candidate Replacement:** `pywebview` using local HTTP server mode.
- **Required Behavior:** Open a native OS window, serve React static files, communicate with FastAPI, handle native File/Save dialogs, shut down Python gracefully on close.
- **Alternatives:** Electron (bloated, +150MB Chromium), PySide6 (heavy Qt dependency).
- **Status:** **Requires PoC.**
- **Rationale:** `pywebview` is vastly lighter than Electron and avoids massive file bloat by using the OS-native webview (Edge WebView2). Binding FastAPI to an ephemeral localhost port (`127.0.0.1:0`) avoids Cross-Origin Resource Sharing (CORS) issues.

### ADR 6: Packaging & Distribution
- **Current:** Docker Compose.
- **Candidate Replacement:** PyInstaller (`onedir` mode) wrapped in a standard Windows Installer (e.g., Inno Setup or NSIS).
- **Required Behavior:** Bundle Python, React dist, and SQLite DLLs into an application directory, installed to `C:\Program Files` with a Start Menu shortcut.
- **Status:** **Proposed / Requires PoC.**
- **Rationale:** The `onefile` approach severely penalizes startup time and reliability. Distributing a standard Windows installer (`.exe` or `.msi`) that writes a `onedir` build to `Program Files` matches expected Windows desktop application UX, guarantees fast startup, and provides a clean upgrade path.

### ADR 7: Search Architecture (SearXNG Removal)
- **Current:** Local SearXNG container via Docker.
- **Candidate Replacement:** `SearchProvider` abstraction supporting multiple backends.
- **Required Behavior:** Provide web search capabilities without requiring local Docker or a complex local Python installation of SearXNG.
- **Status:** **Approved.**
- **Rationale:** The application must satisfy the requirement that search works immediately after installation. We will define an abstract `SearchProvider` interface. The application will use a built-in DuckDuckGo HTML scraper as the default fallback for zero-configuration searches. However, acknowledging the fragility and rate-limiting of HTML scraping, the application will provide first-class support for users to configure reliable API keys (Brave Search, Tavily, Serper.dev) in the Windows Credential Manager.

---

## 9. Migration Dependency Graph

```text
               Phase 1 Architecture Prototyping & Benchmarks
                                     |
    +--------------------------------+--------------------------------+
    |                                |                                |
 Phase 2 Storage                Phase 3 Graph                  Phase 4 Execution
    |                                |                                |
    +--------------------------------+--------------------------------+
                                     |
                       All Migration Foundations Complete
                                     |
                       Phase 5 Workspace File Architecture
                                     |
                       Phase 6 Desktop Shell Integration
                                     |
                       Phase 7 Application Packaging
                                     |
                       Phase 8 Final Verification & E2E
```

---

## 10. Phase Breakdown & Detailed Tasks

### Phase 1: Architecture Prototyping & Benchmarks
- **Objective:** Mitigate the highest risks (ADR 1, ADR 2, ADR 3, ADR 5) via isolated PoCs.
- **Task 1.1 (Graph Benchmark):** Write a SQLite dataset generator (10k nodes, 30k edges). Implement Recursive CTEs and validate pathfinding latency targets.
- **Task 1.2 (Storage Benchmark):** Write an `aiosqlite` script executing the realistic workload (Task 7.1) with `busy_timeout` and WAL. Measure p95/p99 latencies.
- **Task 1.3 (Execution PoC):** Build the `asyncio` task manager prototype to prove lifecycle tracking, cancellation, and non-blocking behavior.
- **Task 1.4 (Desktop PoC):** Create a skeleton `pywebview` app on an ephemeral port.

*(Approval Gate: Do not proceed to Phase 2 until Phase 1 benchmarks prove the architecture)*

### Phase 2: Core Storage Migration
- **Objective:** Port PostgreSQL backend to `aiosqlite`.
- **Dependencies:** Phase 1.
- **Task 2.1 (Schema):** Rewrite schema to SQLite syntax.

### Phase 3: Graph Engine Migration
- **Objective:** Replace Neo4j Cypher queries with local graph traversals using SQLite.
- **Dependencies:** Phase 1.
- **Task 3.1 (Writers):** Rewrite `app/graph/writer.py` to insert extracted nodes and edges into SQLite.
- **Task 3.2 (Readers):** Rewrite `app/graph/reader.py` to replace Cypher queries with SQLite Recursive CTEs (`WITH RECURSIVE`). Implement cycle prevention logic.

### Phase 4: Background Execution Migration
- **Objective:** Remove Celery and Redis dependencies.
- **Dependencies:** Phase 1.
- **Task 4.1 (Execution):** Implement the `asyncio` task manager defined in ADR 3.
- **Task 4.2 (Caching):** Replace Redis calls with `cachetools.TTLCache` and `aiolimiter`.

### Phase 5: Workspace File Architecture
- **Objective:** Implement `.osint` lifecycle (New, Open, Save As, Close).
- **Dependencies:** Phase 2, 3, 4.

### Phase 6: Desktop Shell Integration
- **Objective:** Wrap the backend and frontend into a native window.
- **Dependencies:** Phase 5.

### Phase 7: Application Packaging
- **Objective:** Generate a standalone installer.
- **Dependencies:** Phase 6.

### Phase 8: Final Integration & E2E
- **Objective:** Regression testing.

---

## 11. Final Verification Plan

Before shipping, the packaged `.exe` must pass:
1. **Collector E2E:** A complete investigation against a known safe target completes successfully.
2. **Migration Integrity:** An old investigation JSON export can be imported into the new SQLite format.
3. **Crash/Recovery Test:** Force-killing the `.exe` midway through a pivot round leaves the SQLite database uncorrupted upon reopening (recovering via WAL).
4. **Clean Install:** The executable runs successfully on a pristine Windows 11 Sandbox without any prior Python, Docker, or Node.js installations.
5. **Security Scan:** Backend rejects all SSRF targets, and malicious `.osint` files are safely rejected without executing triggers or extensions.

---

## 12. Open Decisions / Approval Gates
 
 **STOP! The following items require explicit resolution or approval before Phase 2 implementation begins:**
 
 1. **[Requires Benchmark] Storage Layer:** Pass the realistic OSINT workload benchmark (Section 7.1).
 2. **[Requires Benchmark] Graph Engine:** Pass the 10k/50k node recursive CTE benchmark, validating cycle prevention and index behavior (Section 7.2).
 3. **[Requires PoC] Background Execution:** Validate the asyncio task manager lifecycle and cancellation.
 4. **[Requires PoC] Desktop Shell:** Validate `pywebview` integration.
 
 ---
*(End of Specification)*
"""

with open("DESKTOP_MIGRATION_SPEC.md", "w", encoding="utf-8") as f:
    f.write(content)

print("Specification rewritten successfully.")
