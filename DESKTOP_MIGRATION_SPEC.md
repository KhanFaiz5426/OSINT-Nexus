# OSINT Nexus: Desktop Migration Specification

**Version:** 3.0 (Final Architecture Refinement)
**Date:** 2026-09-10
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
- **Desktop Shell:** Technology-neutral container (e.g., `pywebview` or Electron) wrapping the FastAPI instance and React build into a single native window.
- **Storage:** A single `.osint` file (embedded SQLite database) per investigation containing both document data and graph edges.
- **Graph Engine:** Local graph engine (NetworkX in-memory or raw SQLite recursive queries) replacing Neo4j.
- **Task Queue:** Local execution pool (Python `asyncio`) running within the same process.
- **Cache/Rate Limiting:** In-memory Python caching (`cachetools`) and token-bucket limiters.
- **Deployment:** Single packaged executable via PyInstaller or equivalent.

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
- **Save/Atomic Save:** Because it is a live SQLite database, saves are continuous via transactions. "Save As" is accomplished via the SQLite Online Backup API or safe file duplication during a locked state.
- **Open/Close:** Opening a file binds the FastAPI dependency pool to that specific file. Closing it releases locks and connection pools.
- **Corruption/Recovery:** Before opening an existing `.osint` file, the app must create an automatic `.bak` backup copy. SQLite WAL (Write-Ahead Logging) mode must be enabled to prevent corruption during sudden power loss or process crashes.
- **File Locking:** Standard SQLite file locking mechanisms apply. If the file is locked by another process (e.g., opened twice), the app must gracefully deny access.

### 5.3 Versioning & Migrations
- `schema_version` is tracked strictly via SQLite `PRAGMA user_version`. 
- Opening an older `.osint` file automatically triggers sequential migration scripts (similar to Alembic) before allowing read/write access.
- Future compatibility is guaranteed by strict schema immutability for older versions.

### 5.4 Configuration & Secrets (CRITICAL)
- The `.osint` file must **NEVER** contain API keys, LLM tokens, or local path secrets.
- Application-level configuration (theme, API keys, default search providers) remains strictly separated in a global config directory (e.g., `~/.osint-nexus/config.json` or Windows Credential Manager).

---

## 6. Security Architecture

### 6.1 Authentication (Intentionally Out of Scope)
Authentication (JWT/RBAC) is **explicitly removed and intentionally out of scope** for the standalone local product. The application runs on the user's local machine, under their OS user context, binding only to local interfaces. 

### 6.2 Application Security Areas
- **API Bindings:** Local API endpoints must bind strictly to `127.0.0.1` and reject cross-origin requests from non-local domains to prevent drive-by localhost attacks.
- **SSRF Protection:** The existing `security.py` preventing internal network scanning remains strictly enforced. Malicious `.osint` targets cannot be used to map the user's LAN.
- **File Parsing & Injection:** Imported `.osint` files (from untrusted parties) must be handled safely. SQLite PRAGMAs restricting external extensions and preventing malicious trigger execution must be enabled.
- **Path Traversal:** File open/save APIs must strictly validate paths against traversal payloads.

---

## 7. Scalability Requirements

Scalability verification is broken down across physical and logical domains. 
**Target Benchmarks (Large Investigation = 5,000 entities, 15,000 relationships):**

### 7.1 Storage Scalability (SQLite)
- **Load/Open Time:** SQLite database connection and schema verification < 1.0 seconds.
- **Observation Write:** Inserting 100 concurrent JSONB observations < 200ms.
- **File Size:** 15,000 entities + heavy JSON observations must remain < 50MB on disk.

### 7.2 Processing Scalability (Asyncio)
- **Concurrency:** The orchestration loop must comfortably manage 10 concurrent I/O-bound collector tasks without blocking the main event loop.
- **CPU Profiling:** JSON deserialization must not cause event loop lag exceeding 50ms per tick.

### 7.3 Graph Query Scalability
- **Loading:** Loading the entire graph representation from SQLite into memory < 500ms.
- **Multi-Hop Traversal:** Extracting a 4-hop bounded path between two distant nodes < 500ms.
- **Neighbor Retrieval:** 1-hop neighbor lookup < 50ms.

### 7.4 Visualization & UI Scalability
- **Render Time:** Cytoscape rendering up to 2,000 nodes without noticeable UI freezing (< 1.5 seconds).
- **Pagination:** If graph exceeds 2,000 nodes, the UI must gracefully paginate or aggressively cluster nodes by default.

---

## 8. Architectural Decision Records (ADRs)

### ADR 1: Storage Layer
- **Current:** PostgreSQL 16+ via `asyncpg`.
- **Candidate Replacement:** SQLite via `aiosqlite`.
- **Required Behavior:** JSON querying, transactional integrity, concurrent read access.
- **Risks:** SQLite JSON1 syntax differs from Postgres; concurrent writes can hit "database is locked" errors if WAL is not properly tuned.
- **Status:** **Proposed / Requires PoC.**
- **PoC Acceptance Criteria:** Prove robust concurrent JSON inserts using `aiosqlite` with WAL mode enabled.
- **Rollback:** Retain local PostgreSQL via Docker (violates primary goal).

### ADR 2: Graph Engine
- **Current:** Neo4j via AsyncDriver.
- **Candidate Replacement:** Local `NetworkX` in Python, populated from SQLite edge tables.
- **Required Behavior:** 4-hop bounded pathfinding, subgraph extraction, neighbor queries.
- **Alternatives:** Raw SQLite Recursive CTEs, DuckDB.
- **Risks:** Loading 15k edges into NetworkX on every request is inefficient; caching mechanisms may be required. Memory bloat in Python.
- **Status:** **Requires Benchmark.**
- **Benchmark Acceptance Criteria:** Load 10k nodes/30k edges from SQLite and calculate 4-hop paths in < 500ms.

### ADR 3: Background Workers & Execution
- **Current:** Celery + Redis.
- **Candidate Replacement:** Native `asyncio` task pool (`asyncio.create_task` or bounded `asyncio.Semaphore`).
- **Required Behavior:** Concurrent API collection, timeout enforcement, rate-limiting, failure recovery.
- **Risks:** Task crashes taking down the entire FastAPI server; event-loop starvation.
- **Status:** **Proposed / Requires PoC.**
- **PoC Acceptance Criteria:** Successfully execute 50 mock OSINT collections concurrently with timeouts and rate limits, proving the FastAPI web endpoints remain responsive.

### ADR 4: Caching & Rate Limiting
- **Current:** Redis.
- **Candidate Replacement:** `cachetools.TTLCache` (in-memory) + `aiolimiter`.
- **Required Behavior:** Prevent OSINT API bans via strict token buckets; cache repeated queries for 24h.
- **Risks:** Cache disappears on application restart. (Acceptable for an OSINT app).
- **Status:** **Approved.**

### ADR 5: Desktop Shell Integration
- **Candidate Replacements:** `pywebview`, Electron (via HTTP), PySide6 (QWebEngineView).
- **Required Behavior:** Open a native OS window, serve React static files, communicate with FastAPI, handle native File/Save dialogs, shut down Python gracefully on close.
- **Risks:** `pywebview` relies on OS-level browser engines which can introduce rendering inconsistencies. Electron bloats the bundle size heavily.
- **Status:** **Requires PoC.**
- **PoC Acceptance Criteria:** A skeleton app that spawns FastAPI on a random port, opens a native window pointing to it, and cleanly terminates the Python process when the 'X' button is clicked.

### ADR 6: Packaging & Distribution
- **Candidate Replacement:** PyInstaller.
- **Required Behavior:** Bundle Python, React dist, and SQLite DLLs into one `.exe` (Windows).
- **Risks:** PyInstaller struggles with dynamic imports (like the AI and collector registries) and static asset paths. False positives with Antivirus software.
- **Status:** **Requires PoC.**
- **PoC Acceptance Criteria:** Successfully compile and run the backend API from a single `.exe` on a clean Windows VM.

---

## 9. Migration Dependency Graph

```text
[Phase 1] Architecture Prototyping & Benchmarks (Approval Gate)
   |
   +--> (If pass) --> [Phase 2] Core Storage Migration (Postgres -> SQLite)
                         |
                         +--> [Phase 3] Graph Engine Migration (Neo4j -> Local Graph)
                         |       |
                         |       +--> [Phase 4] Execution Migration (Celery -> Asyncio)
                         |               |
                         +---------------+
                                 |
                                 v
                      [Phase 5] Workspace File Architecture (.osint API lifecycle)
                                 |
                                 v
                      [Phase 6] Desktop Shell Integration (pywebview/Electron)
                                 |
                                 v
                      [Phase 7] Application Packaging (PyInstaller)
                                 |
                                 v
                      [Phase 8] Final Verification & E2E
```

---

## 10. Phase Breakdown & Detailed Tasks

### Phase 1: Architecture Prototyping & Benchmarks
- **Objective:** Mitigate the highest risks (ADR 1, ADR 2, ADR 5) via isolated PoCs before touching application code.
- **Why Grouped:** These form the "Approval Gate." No architectural migration should begin until these prove viable.
- **Complexity/Risk:** High.
- **Task 1.1 (Graph Benchmark):** Write a standalone Python script generating a 10k node/30k edge SQLite dataset. Implement Cypher pathfinding logic in `NetworkX`. Measure load/query times.
- **Task 1.2 (Storage Benchmark):** Write an `aiosqlite` script inserting 100 concurrent complex JSONB payloads into a SQLite WAL database. Ensure no lock contention.
- **Task 1.3 (Desktop PoC):** Create a skeleton `pywebview` or PySide6 app that spawns a dummy FastAPI server on a random port and successfully shuts it down on close.
- **Acceptance Criteria:** All benchmarks meet the targets defined in Section 7. Results formally documented.

*(Approval Gate: Do not proceed to Phase 2 until Phase 1 is signed off)*

### Phase 2: Core Storage Migration
- **Objective:** Port the PostgreSQL `asyncpg` backend to `aiosqlite`.
- **Why Grouped:** Modifies the core persistence layer affecting all other data operations. High data-integrity risk.
- **Dependencies:** Phase 1.
- **Task 2.1 (Schema):** Rewrite PostgreSQL Alembic/SQL schema to SQLite syntax. Implement `metadata` table for versioning.
- **Task 2.2 (Connection Pool):** Rewrite `app/db/client.py` to use `aiosqlite`. Implement a dynamic connection manager that binds to a specific `database_path`.
- **Task 2.3 (Queries):** Refactor all CRUD queries in `app/db/` to replace `->>` JSON operators with `json_extract()` and UUIDs with strings.
- **Affected Modules:** `app/db/*`, `alembic/*`.
- **Tests:** Database integrity tests; schema creation; JSON serialization validation.

### Phase 3: Graph Engine Migration
- **Objective:** Replace Neo4j Cypher queries with local graph traversals.
- **Why Grouped:** Isolated, complex algorithmic work replacing a dedicated database technology.
- **Dependencies:** Phase 2.
- **Task 3.1 (Schema Updates):** Add `entities` and `relationships` tables to the SQLite schema.
- **Task 3.2 (Writers):** Rewrite `app/graph/writer.py` to insert extracted nodes and edges into SQLite instead of Neo4j.
- **Task 3.3 (Readers):** Rewrite `app/graph/reader.py` to load edges from SQLite into NetworkX and execute bounded BFS for multi-hop, neighbor, and subgraph queries. Format output identically to existing Cytoscape expected models.
- **Affected Modules:** `app/graph/*`.
- **Tests:** Unit tests comparing old Cypher logic vs new NetworkX logic for neighbor discovery and multi-hop paths.

### Phase 4: Background Execution Migration
- **Objective:** Remove Celery and Redis dependencies.
- **Why Grouped:** Replaces the orchestration and rate-limiting infrastructure.
- **Dependencies:** None (Can run parallel to Phase 2/3).
- **Task 4.1 (Execution):** Remove Celery. Modify `app/api/investigations.py` to trigger `run_investigation_loop` via `asyncio.create_task()`. Ensure exceptions are caught and logged without crashing FastAPI.
- **Task 4.2 (Caching/Limits):** Replace Redis calls in `app/collectors/cache.py` with `cachetools.TTLCache`. Replace Redis rate limiters with `aiolimiter`.
- **Affected Modules:** `app/tasks/*`, `app/core/redis.py`, `app/api/investigations.py`.
- **Tests:** Concurrency stress tests; API rate-limit strictness tests.

### Phase 5: Workspace File Architecture
- **Objective:** Implement the `.osint` file lifecycle (New, Open, Save, Close).
- **Why Grouped:** Establishes how the backend handles state transitions between different databases.
- **Dependencies:** Phase 2.
- **Task 5.1 (API Endpoints):** Create `/api/v1/workspace/new`, `open`, `close`, and `status`.
- **Task 5.2 (State Management):** Implement backend locks preventing multiple `.osint` files from being modified simultaneously by the same process. Handle automatic `.bak` creation on open.
- **Task 5.3 (Frontend Welcome):** Update React to intercept unauthorized API calls if no workspace is active and display a "Start/Open Investigation" landing screen.
- **Affected Modules:** `app/api/workspace.py`, `frontend/src/App.tsx`.
- **Tests:** Save/reopen state persistence tests.

### Phase 6: Desktop Shell Integration
- **Objective:** Wrap the backend and frontend into a native window.
- **Why Grouped:** Specific to OS and window management APIs.
- **Dependencies:** Phase 5, Phase 1 (Desktop PoC).
- **Task 6.1 (Launcher):** Implement `launcher.py` integrating the chosen shell technology (e.g., `pywebview`).
- **Task 6.2 (Lifecycle):** Bind shell close events to graceful FastAPI shutdown.
- **Task 6.3 (Native Dialogs):** Wire frontend "Open File" and "Save File" buttons to trigger native OS file dialogs via desktop shell APIs.
- **Affected Modules:** `launcher.py`, `frontend/*`.

### Phase 7: Application Packaging
- **Objective:** Generate a standalone installer/executable.
- **Why Grouped:** Final distribution mechanics; high probability of edge cases.
- **Dependencies:** Phase 6.
- **Task 7.1 (Build Script):** Write a script to compile React via Vite, copy `dist` to the Python directory, and run PyInstaller.
- **Task 7.2 (PyInstaller Specs):** Ensure all dynamic imports (collectors, AI) and SQLite DLLs are strictly defined in `osint-nexus.spec`.
- **Affected Modules:** `build.py`, `osint-nexus.spec`.
- **Tests:** Execute the `.exe` on a clean Windows VM.

### Phase 8: Final Integration & E2E
- **Objective:** Complete regression testing against the final packaged product.
- **Tasks:** Execute the Final Verification Plan (Section 11).

---

## 11. Final Verification Plan

Before shipping, the packaged `.exe` must pass:
1. **Collector E2E:** A complete investigation against a known safe target completes successfully without API bans.
2. **Migration Integrity:** An old investigation JSON export can be imported into the new SQLite format with zero loss of graph or provenance data.
3. **Crash/Recovery Test:** Force-killing the `.exe` midway through a pivot round preserves the investigation state up to the last successful transaction without SQLite corruption.
4. **Performance/Large Investigation:** Loading a pre-generated `.osint` file with 5,000 nodes renders the graph within 3 seconds and remains interactively responsive.
5. **Clean Install:** The executable runs successfully on a pristine Windows 11 Sandbox without any prior Python, Docker, or Node.js installations.
6. **Security Scan:** Backend rejects all target URLs attempting to resolve to `127.0.0.1`, `169.254.169.254`, or RFC 1918 addresses.

---

## 12. Open Decisions / Approval Gates

**STOP! The following items require explicit resolution or approval before Phase 2 implementation begins:**

1. **[Requires PoC] Desktop Shell Technology:** We must finalize between `pywebview` (lightweight, uses edge/webkit) vs `Electron` (heavier, embeds chromium) vs `PySide6` (Qt-based). 
2. **[Requires Benchmark] Graph Engine Replacement:** We must prove `NetworkX` is performant enough for our max node thresholds (10k nodes, 30k edges, <500ms multi-hop query).
3. **[Requires Benchmark] Storage Layer (JSONB equivalent):** We must prove `aiosqlite` with WAL mode can handle the concurrent JSON observation insertions without database lock contention. 
4. **[Approval] Phasing:** The Phase Breakdown detailed above must be explicitly approved.

---
*(End of Specification)*
